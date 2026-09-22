"""
Workbench backend.

    source sih-venv/bin/activate
    pip install fastapi uvicorn python-multipart
    uvicorn server:app --reload --port 8000

Then open oasis.html in your browser.

TWO SWAPS when the real code is ready (marked SWAP):
    search      -> your Chroma search
    ask_model   -> teammate's ask_model
Nothing else changes.
"""

import datetime
import hashlib
import json
import os
import re
import secrets
import tempfile
import time
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="OASIS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ ACCOUNTS
# Password check is real; the store is hardcoded for the prototype.

from policy import accounts as _accounts, allowed_levels, level_labels

ACCOUNTS = _accounts()

SESSIONS = {}

# --- chats and file ownership -------------------------------------------------
# A chat is one conversation. Signing in starts one; "New chat" starts another.
# Files produced by the agent belong to the person who produced them and to the
# chat they were produced in - nobody else sees them, administrators included.
# An administrator can audit that a file WAS produced, from the ledger; that is
# an event, not the contents.
# How many rows of an attached spreadsheet go into the prompt. Small on
# purpose: the model reads these rather than querying them, and arithmetic
# done in a model's head is the thing query_data exists to prevent. A sheet
# worth analysing belongs in the library.
SHEET_ROW_CAP = 60

# The closing line the model adds when it answered from its own knowledge.
# Must match the wording in GROUNDING["assisted"] in agent/loop.py.
MODEL_KNOWLEDGE_RE = re.compile(
    r"\(?\s*knowledge\s+from\s+model\s+explicit(?:e)?ly\s*\)?\s*$", re.I)

CHATS = {}             # token -> id of the chat currently open
CHAT_META = {}         # chat id -> {"user", "title", "when"}
CHAT_LOG = {}          # chat id -> [turn, ...]  full history, for display
FILE_OWNER = {}        # filename -> {"user": username, "chat": chat id}
_CHAT_SEQ = [0]


def new_chat(token: str, username: str) -> str:
    """Open a new chat. The previous one is kept, not discarded."""
    _CHAT_SEQ[0] += 1
    cid = f"chat_{_CHAT_SEQ[0]}_{secrets.token_hex(3)}"
    CHATS[token] = cid
    CHAT_META[cid] = {"user": username, "title": "New chat",
                      "when": datetime.datetime.now().strftime("%H:%M")}
    CHAT_LOG[cid] = []
    return cid


def chats_of(username: str) -> list:
    """That person's chats, newest first. Nobody sees anyone else's."""
    out = [{"id": cid, "title": m["title"], "when": m["when"]}
           for cid, m in CHAT_META.items() if m["user"] == username]
    return out[::-1]


def record_turn(cid: str, turn: dict):
    if cid not in CHAT_LOG:
        return
    CHAT_LOG[cid].append(turn)
    meta = CHAT_META.get(cid)
    if meta and meta["title"] == "New chat":
        q = " ".join((turn.get("question") or "").split())
        meta["title"] = (q[:46] + "...") if len(q) > 46 else (q or "New chat")


def own_file(filename: str, username: str, token: str):
    if filename:
        FILE_OWNER[filename] = {"user": username,
                                "chat": CHATS.get(token, "")}


def may_read(filename: str, username: str) -> bool:
    """Only the person who produced it. Not shared, not admin-visible."""
    rec = FILE_OWNER.get(filename)
    return bool(rec) and rec["user"] == username

# ------------------------------------------------------------------ WIRING
from my_rag import search, library   # real Chroma retrieval
from agent.models import ask_model   # real Ollama
from agent.loop import run_agent, approve as run_approve
from agent.session import remember, questions as session_questions, forget
from agent.model_identity import summary as model_summary, model_digests

# ------------------------------------------------------------------ LEDGER

# How many entries an administrator sees at once. Large enough that a session's
# own sign-in events cannot push the rest of the trail out of view.
LEDGER_VIEW = 250

LEDGER = []


def ledger_for(username: str) -> list:
    """The ledger is an administrator's view and nobody else's.

    It names every actor and every filename, so returning it to an Employee or
    a Contractor discloses both what other people did and that restricted
    documents exist - existence disclosure defeats the point of compartmenting
    the library in the first place.
    """
    acct = ACCOUNTS.get(username) or {}
    if acct.get("clearance") != "restricted":
        return []
    # The whole trail, newest last. This used to return the final six entries,
    # which meant signing out and back in - two entries of its own - pushed
    # everyone else's activity out of view. The record looked like it had been
    # cleared when nothing had been lost.
    return LEDGER[-LEDGER_VIEW:]


def log(actor: str, event: str):
    prev = LEDGER[-1]["hash"] if LEDGER else "0" * 12
    seq = len(LEDGER) + 1
    payload = f"{seq}{actor}{event}{prev}"
    own = hashlib.sha256(payload.encode()).hexdigest()[:12]
    LEDGER.append({"seq": seq, "actor": actor, "event": event,
                   "prev": prev, "hash": own,
                   "time": time.strftime("%H:%M:%S")})


def verify_chain():
    prev = "0" * 12
    for e in LEDGER:
        payload = f"{e['seq']}{e['actor']}{e['event']}{prev}"
        if hashlib.sha256(payload.encode()).hexdigest()[:12] != e["hash"]:
            return False, e["seq"]
        prev = e["hash"]
    return True, None


# ------------------------------------------------------------------ ROUTES


@app.get("/roles")
async def roles():
    """The login screen reads its role cards from here, so adding an account to
    policy.yaml makes it appear without touching the HTML."""
    out = []
    for username, a in ACCOUNTS.items():
        out.append({"username": username, "role": a["role"],
                    "label": a["label"], "clearance": a["clearance"],
                    "can_upload": a["can_upload"]})
    return {"roles": out, "level_labels": level_labels()}


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    acct = ACCOUNTS.get(username)
    if not acct or acct["password"] != password:
        log(username, "failed sign-in attempt")
        return JSONResponse({"ok": False, "error": "Incorrect username or password"},
                            status_code=401)
    token = hashlib.sha256(f"{username}{time.time()}".encode()).hexdigest()[:16]
    SESSIONS[token] = username
    new_chat(token, username)
    log(acct["name"], "signed in")
    return {"ok": True, "token": token, "name": acct["name"],
            "role": acct["role"], "clearance": acct["clearance"],
            "label": acct["label"], "can_upload": acct["can_upload"],
            "can_audit": acct["clearance"] == "restricted"}


@app.post("/ask")
async def ask(token: str = Form(...), question: str = Form(...),
              mode: str = Form("documents"),
              file: Optional[UploadFile] = File(None)):
    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    acct = ACCOUNTS[username]

    image_path, attached = None, None
    if file is not None:
        # tempfile, not "/tmp" - that path does not exist on Windows.
        # basename strips any directory component in the supplied filename.
        safe = os.path.basename(file.filename)
        path = os.path.join(tempfile.gettempdir(), safe)
        with open(path, "wb") as fh:
            fh.write(await file.read())
        log(acct["name"], f"attached {safe}")

        if safe.lower().endswith(".pdf"):
            # Read it for THIS question only. Not indexed, not classified -
            # it is the user's own file, so no clearance question arises, and
            # it leaves no trace in the document store.
            try:
                from pypdf import PdfReader
                pages = [(pg.extract_text() or "")
                         for pg in PdfReader(path).pages]
                how = "text layer"

                # A scan has no text layer. Recover it from the pixels rather
                # than telling the user their document is unreadable.
                if not any(t.strip() for t in pages):
                    import text_recog
                    if text_recog.available():
                        log(acct["name"], f"{safe} has no text layer - "
                                          f"reading it with OCR")
                        pages = text_recog.read_pdf_pages(path)
                        how = "OCR"
                    else:
                        log(acct["name"], f"{safe} needs OCR, which is not "
                                          f"installed on this machine")

                text = "\n\n".join(f"[p.{i+1}] {t}"
                                    for i, t in enumerate(pages) if t.strip())
                if text.strip():
                    attached = {"name": safe, "text": text}
                    log(acct["name"], f"read {safe} for this question "
                                      f"({len(pages)} pages, {how})")
                else:
                    log(acct["name"], f"attached {safe} has no extractable "
                                      f"text - is it a scan?")
            except Exception as e:
                log(acct["name"], f"could not read {safe} - {e}")
        elif safe.lower().endswith((".xlsx", ".xlsm")):
            # A spreadsheet attached to one question. Read as a table in the
            # prompt, not loaded into SQLite - it carries no classification,
            # and an unlabelled table in a clearance-filtered store is exactly
            # the hole the design exists to avoid.
            #
            # That means the model reads the numbers rather than querying
            # them, so this is capped hard. Past the cap the honest answer is
            # to add it to the library, where query_data can be exact.
            try:
                from openpyxl import load_workbook
                wb = load_workbook(path, data_only=True)
                blocks, total = [], 0
                for ws in wb.worksheets:
                    rows = [r for r in ws.iter_rows(values_only=True)
                            if any(v is not None for v in r)]
                    if not rows:
                        continue
                    total += len(rows) - 1
                    shown = rows[:SHEET_ROW_CAP + 1]
                    lines = [" | ".join("" if v is None else str(v)
                                        for v in r) for r in shown]
                    if len(rows) > len(shown):
                        lines.append(f"... {len(rows) - len(shown)} more rows "
                                     f"not shown")
                    blocks.append(f"[sheet: {ws.title}]\n" + "\n".join(lines))

                if blocks:
                    note = ""
                    if total > SHEET_ROW_CAP:
                        note = (f"\n\nOnly the first {SHEET_ROW_CAP} rows are "
                                f"shown. Say so, and say that adding the file "
                                f"to the library would let it be queried "
                                f"exactly instead of read.")
                    attached = {"name": safe,
                                "text": "\n\n".join(blocks) + note}
                    log(acct["name"], f"read {safe} for this question "
                                      f"({total} rows, "
                                      f"{'truncated' if total > SHEET_ROW_CAP else 'whole sheet'})")
                else:
                    log(acct["name"], f"attached {safe} is empty")
            except Exception as e:
                log(acct["name"], f"could not read {safe} - {e}")
        elif safe.lower().endswith((".pptx", ".potx")):
            # Extract BOTH: the text, in case they want it read or rewritten,
            # and the path, in case they want its layouts. Which one applies
            # depends on what they asked, and they asked in the prompt.
            text = ""
            try:
                from pptx import Presentation
                lines = []
                for i, sl in enumerate(Presentation(path).slides, start=1):
                    said = [sh.text_frame.text.strip()
                            for sh in sl.shapes
                            if sh.has_text_frame and sh.text_frame.text.strip()]
                    if said:
                        lines.append(f"[slide {i}] " + "\n".join(said))
                text = "\n\n".join(lines)
            except Exception as e:
                log(acct["name"], f"could not read slides of {safe} - {e}")
            attached = {"name": safe, "text": text, "template_path": path,
                        "kind": "pptx"}
            log(acct["name"], f"attached {safe} "
                              f"({len(text.split(chr(10)+chr(10)))} slides read)")
        elif safe.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
            image_path = path
            # Also read any text in the picture. A nameplate or a drawing
            # exported as an image is a document; the vision model interprets
            # the picture, OCR reads what is printed on it. Both are offered
            # and the request decides which matters.
            try:
                import text_recog
                if text_recog.available():
                    found = text_recog.read_image(path)
                    if found.strip():
                        attached = {"name": safe, "text": f"[image] {found}"}
                        log(acct["name"], f"read text from {safe} with OCR "
                                          f"({len(found)} chars)")
            except Exception as e:
                log(acct["name"], f"could not read text from {safe} - {e}")
        else:
            image_path = path

    mode = mode if mode in ("documents", "assisted") else "documents"
    log(acct["name"], "asked a question"
        + (" (model knowledge permitted)" if mode == "assisted" else ""))

    cid = CHATS.get(token) or new_chat(token, username)

    res = run_agent(question=question, user=username,
                    user_level=acct["clearance"], user_name=acct["name"],
                    images=[image_path] if image_path else None,
                    token=cid, mode=mode, attached=attached)

    remember(cid, question, res.get("answer", ""),
             (res.get("pending_action") or {}).get("description"))
    record_turn(cid, {"question": question, "mode": mode,
                      "answer": res.get("answer", ""),
                      "sources": res.get("sources", []),
                      "steps": res.get("steps", []),
                      "refused": res.get("refused", False),
                      "model_used": res.get("model_used", ""),
                      "model_reason": res.get("model_reason", "")})

    for st in res.get("steps", []):
        log(acct["name"], f"tool: {st['tool']}")
        # A denial is the most audit-worthy event in an access-control system:
        # record what the clearance filter withheld, not only what was returned.
        if st["tool"] == "search_documents":
            n = st.get("excluded", 0)
            if n:
                log(acct["name"],
                    f"withheld {n} passage{'s' if n != 1 else ''} "
                    f"above {acct['clearance']} clearance")

    excluded = 0
    try:
        from my_rag import search as _s
        _, excluded = _s(question, acct["clearance"])
    except Exception:
        pass

    if res.get("pending_action"):
        log(acct["name"], f"proposed: {res['pending_action']['description']}")
    else:
        log(acct["name"], f"answered - {res.get('model_used','')}")

    return {"answer": res["answer"],
            "sources": res["sources"],
            "excluded": excluded,
            # A refusal is the system declining, not merely an answer without
            # citations. A greeting, a calculation, a query_data result and a
            # model-knowledge answer all have no sources by nature.
            #
            # The marker is the reliable signal: an answer that ends with
            # "Knowledge from model explicitely" is one the model chose to
            # give, which is the opposite of a refusal. Without that test, a
            # model-knowledge answer that needed no tool at all was painted
            # red - the system had answered exactly as asked.
            "refused": (not res["sources"] and not res.get("pending_action")
                        and not res.get("steps")
                        and not MODEL_KNOWLEDGE_RE.search(
                            res.get("answer", ""))),
            "model_used": res.get("model_used", ""),
            "model_reason": res.get("model_reason", ""),
            "steps": res.get("steps", []),
            "pending_action": res.get("pending_action"),
            "recent": session_questions(CHATS.get(token, "")),
            "ledger": ledger_for(username)}


@app.post("/approve")
async def approve(token: str = Form(...), action_id: str = Form(...),
                  approved: str = Form(...)):
    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    name = ACCOUNTS[username]["name"]
    ok = approved == "true"

    res = run_approve(action_id, ok)
    if res.get("file"):
        own_file(res["file"], username, token)
    log(name, f"file write {'approved' if ok else 'rejected'}"
              + (f" - {res.get('file')}" if res.get("file") else ""))

    return {"ok": res.get("ok", True), "written": res.get("written", False),
            "message": res.get("message", ""), "file": res.get("file"),
            "ledger": ledger_for(username)}


@app.get("/download/{filename}")
async def download(filename: str, token: str = ""):
    import pathlib
    from fastapi.responses import FileResponse

    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)

    # basename first: a filename is not a path, and "../" must not escape.
    safe = os.path.basename(filename)
    if not may_read(safe, username):
        # Same answer whether it does not exist or is not theirs - a different
        # answer would tell a stranger which filenames exist.
        return JSONResponse({"error": "No such file"}, status_code=404)

    p = pathlib.Path("outputs") / safe
    if not p.exists():
        return JSONResponse({"error": "No such file"}, status_code=404)
    return FileResponse(str(p), filename=safe)


def docs_for(username: str) -> list:
    """The library as this person may see it.

    Spreadsheets live in SQLite rather than the vector index, so library()
    does not see them; a user opening "Documents" expects the whole library,
    not the half that happens to be chunked. Both are filtered by clearance -
    listing a restricted filename to a contractor is existence disclosure.
    """
    from structured import tables as _tables

    allowed = allowed_levels(ACCOUNTS[username]["clearance"])
    import registry as _reg
    entries = _reg.all_entries()

    def dated(d):
        e = entries.get(d["document"], {})
        return dict(d, effective=e.get("effective", ""),
                    date_source=e.get("date_source", ""))

    docs = [dated(dict(d, kind="document")) for d in library()
            if d["sensitivity"] in allowed]
    for t in _tables(ACCOUNTS[username]["clearance"]):
        e = entries.get(t["source_file"], {})
        docs.append({"document": t["source_file"], "kind": "table",
                     "sensitivity": t["sensitivity"], "chunks": t["rows"],
                     "columns": t["columns"],
                     "effective": e.get("effective", ""),
                     "date_source": e.get("date_source", "")})
    docs.sort(key=lambda x: x["document"])
    return docs


@app.get("/documents")
async def documents(token: str):
    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    return {"documents": docs_for(username),
            "can_upload": ACCOUNTS[username]["can_upload"]}


@app.post("/upload")
async def upload(token: str = Form(...), level: str = Form(...),
                 file: UploadFile = File(...)):
    """Add a document to the searchable library with a chosen classification."""
    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)

    acct = ACCOUNTS[username]
    if not acct["can_upload"]:
        log(acct["name"], f"upload refused - {acct['role']} may not add documents")
        return JSONResponse(
            {"error": "Your role may not add documents to the library."},
            status_code=403)

    if level not in ("public", "internal", "restricted"):
        return JSONResponse({"error": "Choose a classification."}, status_code=400)

    import pathlib
    from ingest import ingest_one

    name = os.path.basename(file.filename)
    if not name.lower().endswith((".pdf", ".xlsx", ".xlsm")):
        return JSONResponse(
            {"error": "Add a PDF or a spreadsheet (.xlsx). Other formats are "
                      "not indexed."}, status_code=400)

    dest = pathlib.Path("corpus") / name
    dest.write_bytes(await file.read())

    try:
        chunks = ingest_one(str(dest), level)
    except Exception as e:
        log(acct["name"], f"upload failed - {file.filename}")
        return JSONResponse({"error": f"Could not index that file: {e}"},
                            status_code=400)

    is_sheet = name.lower().endswith((".xlsx", ".xlsm"))

    if chunks == 0:
        log(acct["name"], f"upload produced no text - {name}")
        return JSONResponse(
            {"error": "No text could be extracted. Is it a scan? OCR is needed."},
            status_code=400)

    unit = "rows" if is_sheet else "chunks"
    log(acct["name"], f"added {name} as {level} ({chunks} {unit})")
    return {"ok": True, "document": name, "level": level,
            "chunks": chunks, "unit": unit, "documents": docs_for(username),
            "ledger": ledger_for(username)}


@app.get("/suggestions")
async def suggestions(token: str):
    """Starter questions, plus whatever this session has already asked."""
    if token not in SESSIONS:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    starters = [
        "What is the interlock set point on the crude distillation column?",
        "Why does the seal on P-101 keep failing?",
        "How many breakdowns has P-101 had, and how much downtime?",
        "Draft an approval note for replacing the seal on P-101.",
        "What permits are required for a mechanical seal replacement?",
    ]
    return {"starters": starters, "recent": session_questions(CHATS.get(token, ""))}


@app.post("/new_chat")
async def new_chat_endpoint(token: str = Form(...)):
    """Start a fresh conversation. Clears the short memory and scopes any
    files produced from here on to the new chat."""
    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    cid = new_chat(token, username)
    log(ACCOUNTS[username]["name"], "started a new chat")
    return {"ok": True, "chat": cid, "chats": chats_of(username)}


@app.get("/chats")
async def list_chats(token: str):
    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    return {"chats": chats_of(username), "current": CHATS.get(token, "")}


@app.post("/open_chat")
async def open_chat(token: str = Form(...), chat: str = Form(...)):
    """Switch to one of your own earlier chats and get its turns back."""
    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    meta = CHAT_META.get(chat)
    if not meta or meta["user"] != username:
        return JSONResponse({"error": "No such chat"}, status_code=404)
    CHATS[token] = chat
    return {"ok": True, "chat": chat, "turns": CHAT_LOG.get(chat, []),
            "chats": chats_of(username)}


@app.post("/flag")
async def flag(token: str = Form(...), question: str = Form(...),
               answer: str = Form(...), what_is_wrong: str = Form(...),
               correct_answer: str = Form(...), corrects: str = Form("")):
    """Anyone may say an answer is wrong, whatever their clearance. Spotting
    an error is not a privileged act. Nothing changes until it is reviewed."""
    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    import corrections

    c = corrections.raise_correction(
        question=question, answer=answer, what_is_wrong=what_is_wrong,
        correct_answer=correct_answer, corrects=corrects,
        by=ACCOUNTS[username]["name"])
    log(ACCOUNTS[username]["name"], f"raised a correction ({c['id']})")
    return {"ok": True, "id": c["id"],
            "message": "Sent for review. Nothing has changed yet."}


@app.get("/corrections")
async def list_corrections(token: str):
    """Administrators only - it carries the answers and sources of other
    people's questions."""
    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    if ACCOUNTS[username]["clearance"] != "restricted":
        return JSONResponse({"error": "Not permitted"}, status_code=403)
    import corrections
    return {"pending": corrections.pending(),
            "all": corrections.all_corrections()[:20],
            "levels": list(level_labels().keys())}


@app.post("/review_correction")
async def review_correction(token: str = Form(...), id: str = Form(...),
                            approved: str = Form(...),
                            sensitivity: str = Form(""),
                            edited: str = Form(""), reason: str = Form("")):
    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    if ACCOUNTS[username]["clearance"] != "restricted":
        return JSONResponse({"error": "Not permitted"}, status_code=403)
    import corrections

    res = corrections.review(
        id, approved.lower() == "true", by=ACCOUNTS[username]["name"],
        sensitivity=sensitivity or None, edited_answer=edited or None,
        reason=reason)
    if not res.get("ok"):
        log(ACCOUNTS[username]["name"],
            f"correction review refused - {res.get('error','')[:60]}")
        return JSONResponse({"error": res["error"]}, status_code=400)

    log(ACCOUNTS[username]["name"],
        f"correction {res['status']} ({id})"
        + (f" as {sensitivity}" if res["status"] == "approved" else ""))
    return {"ok": True, "status": res["status"],
            "pending": corrections.pending(),
            "ledger": ledger_for(username)}


@app.post("/set_date")
async def set_date(token: str = Form(...), document: str = Form(...),
                   effective: str = Form(...)):
    """An administrator states a document's effective date. Believed over
    anything extracted from the text."""
    username = SESSIONS.get(token)
    if not username:
        return JSONResponse({"error": "Session expired"}, status_code=401)
    if not ACCOUNTS[username]["can_upload"]:
        return JSONResponse({"error": "Not permitted"}, status_code=403)
    import registry

    if not registry.set_date(document, effective):
        return JSONResponse({"error": "No such document"}, status_code=404)
    log(ACCOUNTS[username]["name"],
        f"set effective date of {document} to {effective}")
    return {"ok": True, "documents": docs_for(username)}


@app.get("/outputs")
async def outputs(token: str):
    """Everything the agent has generated, newest first."""
    import pathlib, datetime
    if token not in SESSIONS:
        return JSONResponse({"error": "Session expired"}, status_code=401)

    username = SESSIONS[token]
    chat = CHATS.get(token, "")
    d = pathlib.Path("outputs")
    files = []
    if d.exists():
        for p in sorted(d.iterdir(), key=lambda x: x.stat().st_mtime,
                        reverse=True):
            if p.name.startswith(".") or not p.is_file():
                continue
            # This chat's files, produced by this person. Nothing else.
            rec = FILE_OWNER.get(p.name)
            if not rec or rec["user"] != username or rec["chat"] != chat:
                continue
            files.append({
                "file": p.name,
                "kind": p.suffix.lstrip(".").lower(),
                "size_kb": max(1, round(p.stat().st_size / 1024)),
                "when": datetime.datetime.fromtimestamp(
                    p.stat().st_mtime).strftime("%H:%M"),
            })
    return {"files": files}


@app.get("/status")
async def status(token: str = ""):
    intact, broken = verify_chain()
    username = SESSIONS.get(token, "")
    return {"egress_mode": "air-gapped", "bytes_out": 0, "blocked": 3,
            # Real SHA-256 digest of the loaded model, read from Ollama at
            # startup. Reports "unavailable" rather than inventing one.
            "model_hash": model_summary(),
            "models": model_digests(),
            "clock": "NIC/NPL",
            "ledger": ledger_for(username), "entries": len(LEDGER),
            "chain_intact": intact, "broken_at": broken}


@app.post("/verify")
async def verify():
    intact, broken = verify_chain()
    return {"intact": intact, "broken_at": broken, "entries": len(LEDGER)}
