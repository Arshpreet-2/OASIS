# OASIS — Setup and Demo Runbook

Everything needed to get this running on a machine that has never seen the
project. Written so that someone who was not there when it was built can follow
it.

**Keep a copy of this on a USB stick with the project folder.**

---

## PART 1 — WHAT THE PROJECT IS MADE OF

    oasis/
      oasis.html    the interface — opens in a browser, no build step
      server.py         the backend — login, search, ask, ledger, approvals
      policy.yaml       accounts, clearance levels, document classifications
      agent/            models.py, tools.py, loop.py - the agent layer
      outputs/          documents the agent generates
      policy.py         reads policy.yaml
      my_rag.py         retrieval — Chroma search with the clearance filter
      ingest.py         run by hand to load documents into the search index
      make_corpus.py    generates the synthetic demo documents
      agent/models.py   the model layer — ask_model()
      corpus/           the PDFs the system searches
      sih-venv/         the Python virtual environment (NOT copied between machines)
      chroma/           the search index, created when documents are ingested
      REGISTRY.md       what every file does, and what changed when
      RAG_GUIDE.md      how the retrieval layer works
      OWNERSHIP.md      who builds what
      PUSH_TO_GITHUB.md git setup and daily workflow

Two things run at the same time:

  1. `server.py` — started from the terminal, keeps running, serves on port 8000
  2. `oasis.html` — opened in a browser, talks to the server on port 8000

If the browser says "cannot reach the server", the terminal part is not running.

---

## PART 2 — WHAT TO INSTALL, AND WHY

Install in this order. Each line says what it is for, so nothing is installed
without a reason.

| # | Install | Why it is needed |
|---|---------|------------------|
| 1 | **Python 3.11+** | Everything on the backend is Python. Mac has it already; on Windows install from python.org and tick "Add to PATH". |
| 2 | **A virtual environment** | Keeps this project's packages separate from everything else on the machine. Without it, Mac blocks installs with "externally-managed-environment". |
| 3 | **fastapi** | Provides the `/login`, `/ask`, `/approve` endpoints the browser calls. |
| 4 | **uvicorn** | The program that actually runs the FastAPI server. |
| 5 | **python-multipart** | Lets the server receive form data and uploaded files. Without it, login fails with a confusing error. |
| 6 | **chromadb** | The vector database. Stores document chunks and does the search. |
| 6a | **pyyaml** | Reads `policy.yaml` — the accounts, clearance levels and document classifications. Without it the server will not start. |
| 7 | **pypdf** | Reads text out of PDF files during ingestion. |
| 8 | **ollama** (the app) | Runs the AI models locally. Download from ollama.com — it is an application, not a pip package. |
| 9 | **ollama** (the Python package) | Lets our Python code talk to the Ollama app. |
| 10 | **python-docx** | Only needed if generating Word file output. |
| 11 | **reportlab** | Only needed to regenerate the synthetic demo documents. |

---

## PART 3 — FIRST-TIME SETUP ON A NEW MACHINE

### Mac

    cd ~/Desktop
    # copy the oasis folder here from the USB stick, then:
    cd oasis

    python3 -m venv sih-venv
    source sih-venv/bin/activate

    pip install -r requirements.txt

**Important:** do NOT copy `sih-venv` from another machine. It stores absolute
paths and breaks. Delete it and recreate it as above.

### Windows

    cd Desktop\oasis

    python -m venv sih-venv
    sih-venv\Scripts\activate

    pip install -r requirements.txt

If `python` is not recognised, Python was installed without "Add to PATH" —
reinstall and tick that box.

### Then, on either platform

1. Install the Ollama app from ollama.com and open it once.
2. Download the models (several GB, do this well before the demo):

       ollama pull qwen3:4b
       ollama pull qwen2.5vl:3b

3. Generate the demo documents (only if `corpus/` is empty):

       python make_corpus.py

   This writes five synthetic PDFs — a pump manual, a maintenance log, an SOP,
   an inspection report, and a HAZOP report marked RESTRICTED. Every one carries
   a line stating it is synthetic and no sponsor data is used. Leave that line in.

4. Build the search index from the documents:

       python ingest.py corpus/

---

## PART 3B — THE POLICY FILE

`policy.yaml` holds everything an administrator would normally change. Nothing
about accounts or document classification lives in the code.

### What is in it

**Clearance levels**, lowest first. A user retrieves their own level and
everything below it.

    levels:
      - public
      - internal
      - restricted

Adding a fourth level is a matter of putting it in this list in the right
position. No code changes anywhere.

**Accounts.** Each carries a password, a display name, a role, a clearance, the
label shown on screen, and whether that person may add documents to the library.

    accounts:
      admin:
        password:   "123"
        name:       R. Sharma
        role:       Administrator
        clearance:  restricted
        label:      Full access
        can_upload: true

**Document classifications.** Which level each file carries. Anything not listed
falls back to `default_level`.

    documents:
      hazop_report.pdf:         restricted
      pump_manual_p101.pdf:     internal
      sop_seal_replacement.pdf: public

**Retrieval settings.** Chunk size, overlap, and how many passages come back per
question.

### Making a change — and what to do afterwards

This is the part people get wrong. The classification is stored on every chunk
inside the search index, so changing the file alone is not enough.

| What changed | What to do |
|---|---|
| An account — password, name, clearance, upload rights | Restart the server |
| A clearance level added or renamed | Restart the server, then re-ingest |
| A document's classification | Restart the server, then re-ingest |
| Chunk size or overlap | Re-ingest |
| Nothing in policy.yaml, just new PDFs in `corpus/` | Re-ingest |

Restart the server:

    Ctrl+C in the terminal running it, then
    uvicorn server:app --port 8000

Re-ingest:

    python ingest.py corpus/

Re-ingesting clears the index and rebuilds it, so running it twice is harmless.
It prints a chunk count per document and then a check confirming each role sees
progressively less.

### Adding documents without editing the file

An administrator can add and classify a document from the **Documents** tab in
the app. That writes the classification, indexes the file immediately, and
records the action in the audit ledger — no restart, no re-ingestion.

Employees and contractors do not see the uploader at all. Attaching a file to a
single question is still available to everyone from the composer, and that is a
different thing: an attachment is used for one question and never enters the
searchable library.

### The three accounts as shipped

| Role | Username | Password | Can retrieve | Can upload |
|------|----------|----------|--------------|------------|
| Administrator | `admin` | `123` | everything | yes |
| Employee | `employee` | `123` | public and internal | no |
| Contractor | `contractor` | `123` | public only | no |

---

## PART 4 — RUNNING IT (EVERY TIME)

Two terminal commands and one double-click.

**Terminal — start the backend and leave it running:**

    cd ~/Desktop/oasis          # Mac
    source sih-venv/bin/activate    # Mac
    uvicorn server:app --port 8000

    cd Desktop\oasis            # Windows
    sih-venv\Scripts\activate       # Windows
    uvicorn server:app --port 8000

You should see `Uvicorn running on http://127.0.0.1:8000`. Leave this window
open — closing it stops the server.

**Browser — open the interface:**

Double-click `oasis.html`.

**Sign in:**

| Role | Username | Password |
|------|----------|----------|
| Administrator — full access | `admin` | `123` |
| Employee — internal access | `employee` | `123` |
| Contractor — public access | `contractor` | `123` |

Clicking a role card on the login screen fills the username automatically.

---

## PART 5 — DEMO DAY CHECKLIST

Run through this the night before, and again an hour before presenting.

**The evening before**

- [ ] Project folder copied to the demo machine (not just the USB stick)
- [ ] Virtual environment created fresh on that machine
- [ ] All packages installed
- [ ] Ollama installed and both models downloaded — this is the slowest step
- [ ] Documents ingested; the index folder exists
- [ ] Full demo run through end to end at least three times
- [ ] Backup video recorded of the whole demo, in case the live run fails
- [ ] Laptop charger packed

**One hour before**

- [ ] Server starts without errors
- [ ] `oasis.html` opens and the login page appears
- [ ] Both accounts sign in successfully
- [ ] Ask the demo question as Security Admin — sources appear
- [ ] Ask the same question as Employee — one document excluded
- [ ] Ask the same question as Contractor — more excluded, fewer sources
- [ ] Documents tab shows the library with classification badges
- [ ] Uploader is visible for Administrator and absent for the other two
- [ ] Verify chain button returns "chain intact"
- [ ] Test file attachment with the prepared scan
- [ ] Browser zoom set so text is readable from the back of the room
- [ ] Theme chosen and tested on the projector — dark reads better on most
      projectors, light reads better on bright screens. Decide beforehand; the
      toggle is top right, labelled Dark / Light.
- [ ] Notifications and Do Not Disturb turned on
- [ ] Wi-Fi ON for now — it gets turned off during the demo, deliberately

---

## PART 6 — THE DEMO SEQUENCE

Roughly six minutes. Practise until it needs no thinking.

1. **Sign in as Security Admin.** Show the login, mention that passwords are
   really checked and a failed attempt is logged.

2. **Ask the main question.** Point at the sources — each resolves to a real
   document and page.

3. **Attach the scanned report** with the `+` button. Note that it is used for
   this question only and never enters the searchable library.

4. **Approve the file write.** The agent states what it intends to do and waits.
   Nothing happens without a person.

4a. **Open the Documents tab** and upload a document as Restricted, in front of
   them. Ask a question about it — it answers with a citation. This is the
   strongest moment available: a judge can hand you a file they brought.

5. **Sign out. Sign in as Contractor. Ask the identical question.**
   The red "excluded by clearance" tag appears and the answer changes.
   *This is the most important moment — pause here.*

6. **Open the Security panel** with the button top right, point at the egress
   mode and the zero bytes out, then turn Wi-Fi off and ask another question.
   It still works. The panel stays hidden until opened — mention that it is
   there for the security officer, not cluttering the engineer's screen.

7. **Switch to the Audit ledger tab** in the same panel and press Verify chain.
   Show it is intact, and explain that editing any past entry would break the
   chain and be named to the exact row.

---

## PART 7 — WHEN SOMETHING BREAKS

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Cannot reach the server. Is it running on port 8000?" | Backend not running, or it crashed | Look at the terminal, restart `uvicorn server:app --port 8000` |
| `externally-managed-environment` on install | Installing outside a virtual environment | Create and activate the venv first |
| `command not found: pip` | Virtual environment not activated | Run the `activate` line again |
| `ModuleNotFoundError: fastapi` | Wrong environment active, or packages not installed | Activate the venv, reinstall |
| `Address already in use` | An old server is still running | Use a different port (`--port 8001`) and change `const API` in oasis.html, or close the old terminal |
| Answers are very slow | Large model on a CPU | Use the smaller model; say openly that the demo machine has no GPU |
| Ollama connection refused | The Ollama app is not open | Open Ollama, then retry |
| Login works but questions fail | `python-multipart` missing | `pip install python-multipart` |

**The rule for demo day:** if something breaks and is not fixed within two
minutes, switch to the backup video and keep talking. Do not debug in front of
the panel.

---

## PART 8 — WHAT IS REAL AND WHAT IS STUBBED

State this honestly if asked. Being precise here is worth more than pretending.

**Real:** password checking, the clearance filter applied inside the retrieval
query, page-level citations, the hash-chained ledger and its verification,
approval before any file is written, local model inference with no external
calls.

**Stubbed or simplified for the prototype:** the user store is a YAML file
rather than a corporate directory service; three clearance levels are configured
where a plant might use four or five, though the count is a setting rather than a
limit.

**Designed but not built:** the offline client mode, controlled-egress mode with
query sanitisation, approval workflow for configuration changes, signed update
bundles. All are specified in the requirements document.

---

## PART 9 — WHERE THE REAL CODE LIVES

Both stubs have been replaced. `server.py` now imports:

    from my_rag import search, library      # real Chroma retrieval
    from agent.models import ask_model      # real Ollama inference

The signatures, if either is ever rewritten:

    search(question, user_level, k) -> (passages, excluded_count)
        passage = {"text", "document", "page", "sensitivity"}

    ask_model(prompt, images) -> (answer, model_used, model_reason)

    library() -> [{"document", "sensitivity", "chunks"}]

`agent/loop.py` is still unbuilt — the multi-step agent loop with tool calls. The
approval flow in the interface works, but the action it proposes is fixed rather
than chosen by an agent.
