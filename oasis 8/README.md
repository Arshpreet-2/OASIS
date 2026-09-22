# OASIS

SIH 2026 · Problem statement SIH26117 · Sponsor: MRPL

An on-premise AI workbench for confidential industrial documents. Runs entirely
on the plant's own hardware with open-weight models — no cloud, no external
calls.

## Run it

    python3 -m venv sih-venv
    source sih-venv/bin/activate        # Windows: sih-venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn server:app --port 8000

Then open `oasis.html` in a browser (double-click it).

## Sign in

| Role | Username | Password | Can retrieve | Can upload |
|------|----------|----------|--------------|------------|
| Administrator | `admin` | `123` | everything | yes |
| Employee | `employee` | `123` | public and internal | no |
| Contractor | `contractor` | `123` | public only | no |

Clicking a role card on the login screen fills the username. The cards are built
from `policy.yaml` — add an account there and it appears on the login screen.

## Files

| File | What it is |
|------|-----------|
| `oasis.html` | The interface. Opens in a browser, no build step. Light and dark themes. |
| `server.py` | Backend — login, retrieval, ledger, approvals. |
| `my_rag.py` | Retrieval. Chroma search with the clearance filter. |
| `ingest.py` | Run by hand to load documents into the index. |
| `make_corpus.py` | Generates the synthetic demo documents. |
| `agent/models.py` | Model layer — `ask_model()`. |
| `corpus/` | Documents the system searches. Not committed. |
| `SETUP.md` | Full setup and demo-day runbook. **Read this first.** |
| `RAG_GUIDE.md` | How to build the retrieval layer. |
| `OWNERSHIP.md` | Who builds what, and in what order. |
| `PUSH_TO_GITHUB.md` | Git setup and the daily workflow. |

## What is real

Password checking, clearance filtering applied inside the retrieval query,
page-level citations, hash-chained tamper-evident ledger, human approval before
any file is written, local inference with no external calls.

## Interfaces

If any part is ever rewritten, these are the shapes the rest of the system
expects:

    search(question, user_level, k) -> (passages, excluded_count)
        passage = {"text", "document", "page", "sensitivity"}

    ask_model(prompt, images) -> (answer, model_used, model_reason)

    run_agent(question, user, user_level, user_name, images) -> dict
        {"answer", "sources", "steps", "pending_action",
         "model_used", "model_reason"}

    library() -> [{"document", "sensitivity", "chunks"}]

See `REGISTRY.md` for what every file does.
