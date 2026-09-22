"""
Reads policy.yaml. Import this instead of hardcoding accounts or classifications.

    from policy import POLICY, accounts, level_of, allowed_levels
"""

import pathlib
import yaml

_PATH = pathlib.Path(__file__).with_name("policy.yaml")


def load():
    with open(_PATH) as fh:
        return yaml.safe_load(fh)


POLICY = load()


def reload():
    """Re-read the file. Used after the Documents tab writes a change."""
    global POLICY
    POLICY = load()
    return POLICY


def accounts():
    return POLICY["accounts"]


def levels():
    return POLICY["levels"]


def level_labels():
    return POLICY.get("level_labels", {l: l.title() for l in levels()})


def level_of(filename: str) -> str:
    """Classification for a document, or the default."""
    return POLICY["documents"].get(filename, POLICY.get("default_level", "internal"))


def allowed_levels(user_level: str):
    """A user's own level plus everything below it."""
    L = levels()
    if user_level not in L:
        user_level = L[0]
    return L[:L.index(user_level) + 1]


def set_document_level(filename: str, level: str):
    """Write a classification back to policy.yaml, preserving the file."""
    text = _PATH.read_text()
    data = yaml.safe_load(text)
    data.setdefault("documents", {})[filename] = level

    # rewrite only the documents block so comments elsewhere survive
    lines = text.splitlines()
    out, in_docs = [], False
    for ln in lines:
        if ln.startswith("documents:"):
            in_docs = True
            out.append("documents:")
            width = max((len(k) for k in data["documents"]), default=20) + 1
            for k, v in sorted(data["documents"].items()):
                out.append(f"  {(k + ':').ljust(width + 1)} {v}")
            continue
        if in_docs:
            if ln.startswith(" ") or ln.strip() == "":
                if ln.strip() == "":
                    in_docs = False
                    out.append(ln)
                continue
            in_docs = False
        out.append(ln)

    _PATH.write_text("\n".join(out) + "\n")
    reload()


def retrieval(key, default=None):
    return POLICY.get("retrieval", {}).get(key, default)
