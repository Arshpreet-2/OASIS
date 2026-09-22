"""Tool: run Python in a sandbox. STATE-CHANGING - needs approval first.

Some questions cannot be answered by SQL. A count, a total, an average are
SELECT statements; a trend line, a correlation, a distribution are not. This
tool exists for that gap, and only that gap - if query_data can answer it,
query_data should.

Running code a language model wrote is dangerous. Not maliciously - a small
model will simply do something wrong - but the consequences are the same. So
the code runs inside a container with nothing in it:

    --network none      no route out. Not a blocked domain list, no interface
    --read-only         the container filesystem cannot be written to
    --memory 512m       cannot exhaust the host
    --pids-limit 128    cannot fork bomb
    --cap-drop ALL      no privileged operations
    --user 65534:65534  runs as nobody
    timeout             killed after RUN_TIMEOUT seconds, always

The data the code needs is handed to it as a CSV on a read-only mount. The
corpus, the vector index, policy.yaml and the source of the application itself
are not in the container, so code cannot read them however it is written.

Two layers, not one: a person reads the code and approves it, AND even an
approved mistake is contained. changes_state is True, so the approval gate the
rest of the system already uses applies here without special handling.
"""

import json
import pathlib
import shutil
import subprocess
import tempfile

IMAGE = "python:3.12-slim"
RUN_TIMEOUT = 10          # seconds of wall clock, enforced by docker and here
MAX_OUTPUT = 4000         # characters returned to the model
MAX_ROWS = 5000           # rows handed to the code as data


def available() -> tuple:
    """(usable, reason). Docker is optional; the rest of the system works
    without it and says so rather than failing."""
    if not shutil.which("docker"):
        return False, "Docker is not installed on this machine."
    try:
        r = subprocess.run(["docker", "image", "inspect", IMAGE],
                           capture_output=True, timeout=10)
        if r.returncode != 0:
            return False, (f"The sandbox image is missing. Run: "
                           f"docker pull {IMAGE}")
    except Exception as e:
        return False, f"Docker is installed but not responding ({e})."
    return True, ""


def _write_data(folder: pathlib.Path, sql: str, user_level: str) -> str:
    """Run the query at the caller's clearance and leave the rows as a CSV.

    The query goes through run_query like any other, so a table above the
    caller's level is no more readable from inside the container than from
    outside it.
    """
    import csv

    from structured import run_query

    result = run_query(sql, user_level)
    if result.get("error"):
        return result["error"]

    rows = result.get("rows", [])[:MAX_ROWS]
    with open(folder / "data.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(result.get("columns", []))
        w.writerows(rows)
    return ""


def tool_run_code(code: str = "", sql: str = "", user_level: str = "public",
                  **_ignored):
    ok, why = available()
    if not ok:
        return {"error": why}

    if not code.strip():
        return {"error": "No code was supplied."}

    work = pathlib.Path(tempfile.mkdtemp(prefix="oasis-sandbox-"))
    try:
        if sql.strip():
            problem = _write_data(work, sql, user_level)
            if problem:
                return {"error": problem}

        (work / "main.py").write_text(code)

        cmd = [
            "docker", "run", "--rm",
            "--network", "none",              # no route out at all
            "--read-only",                    # container fs is immutable
            "--tmpfs", "/tmp:size=16m",       # somewhere to scribble
            "--memory", "512m", "--memory-swap", "512m",
            "--pids-limit", "128",
            "--cpus", "1",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--user", "65534:65534",
            "-v", f"{work}:/work:ro",         # the code and its data, read-only
            "-w", "/work",
            IMAGE,
            "python", "-I", "main.py",
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=RUN_TIMEOUT + 5)
        except subprocess.TimeoutExpired:
            return {"error": f"The code ran for more than {RUN_TIMEOUT} "
                             f"seconds and was stopped."}

        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()

        if proc.returncode != 0:
            # The traceback goes back to the model so it can correct itself.
            return {"ok": False, "exit_code": proc.returncode,
                    "stdout": out[:MAX_OUTPUT],
                    "error": err[-MAX_OUTPUT:] or "The code failed."}

        if not out:
            return {"ok": True, "stdout": "",
                    "message": "The code ran and printed nothing. Print the "
                               "result you want reported."}

        return {"ok": True, "stdout": out[:MAX_OUTPUT],
                "truncated": len(out) > MAX_OUTPUT,
                "message": "Code ran in the sandbox."}
    finally:
        shutil.rmtree(work, ignore_errors=True)
