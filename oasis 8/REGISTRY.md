# File registry

What every file in this project is for, and what has changed.

Keep this current. When a file is added, add a row. When a file changes in a way
that matters, add a line to the change log at the bottom.

---

## Running code

| File | Purpose | Owner |
|------|---------|-------|
| `oasis.html` | The entire interface. Login, chat, citations, approval prompt, security panel, documents tab, light and dark themes. Opens in a browser, no build step. Talks to the server on port 8000. | frontend |
| `server.py` | The backend. Endpoints for roles, login, ask, approve, upload, documents, status, verify and download. Holds sessions and the hash-chained ledger. Imports retrieval and the agent; contains no business logic of its own. | frontend |
| `policy.yaml` | **Everything an administrator would change.** Clearance levels, accounts with their passwords and permissions, document classifications, chunk settings. No account or classification lives in code. | shared |
| `policy.py` | Reads `policy.yaml` and exposes it. `accounts()`, `levels()`, `level_of(filename)`, `allowed_levels(user_level)`. | shared |
| `structured.py` | **Spreadsheets, kept out of the vector store.** Loads `.xlsx` into SQLite and runs read-only queries against it. Enforces the clearance filter on tables, refuses anything that is not a `SELECT`, and only shows the model the schema of tables it may reach. | retrieval |
| `agent/session.py` | Session memory. The last three turns as question plus a one-line gist, so a follow-up can resolve "that" or "those". Within-session only. | agent |
| `my_rag.py` | Retrieval. `search(question, user_level, k)` queries Chroma **with the clearance filter inside the query**, so material above a user's level is never fetched. Also `library()` for the documents tab. | retrieval |
| `ingest.py` | Run by hand: `python ingest.py corpus/`. Reads PDFs page by page, chunks them, labels each chunk from `policy.yaml`, stores in Chroma. Ends with a check proving each role sees progressively less. Also `ingest_one()`, used by the upload endpoint. | retrieval |
| `agent/models.py` | Talks to Ollama. `ask_model(prompt, images)` returns `(answer, model_used, model_reason)`. Routes by deterministic rule — image means vision, calculation means coder, otherwise general. Model names live in `MODELS`, never in logic. | agent |
| `agent/tools.py` | **The registry only.** Which tools exist, what arguments they take, and whether each one changes state. Roughly 70 lines — the tools themselves live in `agent/tools_impl/`. | agent |
| `agent/tools_impl/search.py` | Tool: search the library. Read-only. | agent |
| `agent/tools_impl/calculate.py` | Tool: exact arithmetic, restricted by regex so no arbitrary code runs. Read-only. | agent |
| `agent/tools_impl/query_data.py` | Tool: SQL over the spreadsheets. Read-only, clearance enforced. | agent |
| `agent/tools_impl/write_docx.py` | Tool: Word document. Needs approval. | agent |
| `agent/tools_impl/write_pptx.py` | Tool: PowerPoint deck. Needs approval. | agent |
| `agent/tools_impl/write_xlsx.py` | Tool: spreadsheet. Needs approval. | agent |
| `agent/tools_impl/templates.py` | `find_template()` — looks up the organisation's own format for a document type before it is written. | agent |
| `agent/tools_impl/_common.py` | Shared by the tool files. The output directory, and nothing else. | agent |
| `agent/loop.py` | The agent loop. Plan, call a tool, observe, repeat, capped at six steps. **Proposal mode:** state-changing tools are never executed — they are returned as `pending_action` and run only after `approve()`. Before proposing, it looks up the house template and gives the model one turn to follow it. | agent |
| `agent/__init__.py` | Marks `agent/` as a package. Empty by design. | agent |

## Data and generated files

| Path | Purpose |
|------|---------|
| `corpus/` | The PDFs the system searches. Five synthetic documents ship with the project. Add more here and re-ingest. |
| `chroma/` | The search index. Created by `ingest.py`, rebuilt on every run. Not committed — delete it freely. |
| `outputs/` | Documents the agent generates. Served by `/download/{filename}`. Not committed. |
| `make_corpus.py` | Regenerates the five synthetic plant PDFs. Only needed if `corpus/` is emptied. |
| `make_templates.py` | Regenerates the three house templates — approval note, letter, report. These live in `corpus/` like any other document. |
| `make_workbook.py` | Regenerates the synthetic maintenance workbook — fifteen work orders with dates, equipment, downtime and cost. |
| `data.db` | SQLite. Spreadsheets loaded by `ingest.py`. Rebuilt on every run, not committed. |

## Documentation

| File | Purpose | Read it when |
|------|---------|--------------|
| `README.md` | What the project is, how to run it, the accounts, the interfaces between parts. | first |
| `SETUP.md` | Full setup for a machine that has never seen the project, the policy file explained, the demo-day checklist, the demo sequence, and what to do when something breaks. | before demo day |
| `REGISTRY.md` | This file. What every file does, and what changed when. | when lost |
| `RAG_GUIDE.md` | How the retrieval layer works and how to change it. Chunking, the clearance filter, tuning, common faults. | when touching retrieval |
| `OWNERSHIP.md` | Who owns what, and the two pieces still unbuilt. | when dividing work |
| `PUSH_TO_GITHUB.md` | Git setup, the daily workflow, and what never to commit. | when setting up the repo |
| `requirements.txt` | Every Python package with a note on why it is needed. | when installing |
| `.gitignore` | Keeps the virtual environment, model files, the index and generated outputs out of the repository. | never, but do not delete it |

---

## Adding a tool

Three steps, and nothing else in the system changes:

1. Write `agent/tools_impl/<name>.py` with one function.
2. Import it at the top of `agent/tools.py`.
3. Add a row to `TOOLS` — crucially including `changes_state`.

If `changes_state` is `True`, the agent will propose it rather than run it, and
the approval flow handles the rest automatically.

---

## The three rules that matter

**The clearance filter goes inside the query.** In `my_rag.py`, the `where=`
clause tells Chroma not to look at material above the user's level. Filtering
results afterwards looks identical in a demo and is not secure.

**State-changing tools are proposed, not executed.** In `agent/loop.py`, any
tool with `changes_state: True` stops the loop and returns a `pending_action`.
Nothing is written until a person approves.

**Tables are queried, not chunked.** Spreadsheets go into SQLite via
`structured.py`. Chunking a sheet separates a header from its rows and answers
counts and totals badly — so `query_data` runs real SQL instead, and the model is
told never to search for a number a query would answer exactly.

**Document formats come from the corpus, not from code.** `find_template()`
searches for the organisation's own template before a document is written. Upload
a new template through the Documents tab and the system starts following it —
no code change, no prompt change. The format guidance in the prompt is only a
fallback for when no template exists.

---

## What is not built

**Sandboxed code execution.** One of the sponsor's four acceptance
demonstrations. Needs a Docker container — no network, read-only mounts, memory
and time limits. The `calculate` tool covers the principle.

**Real egress numbers.** The sovereignty panel shows fixed values. Making them
real needs default-deny firewall rules with logging, and `/status` reading the
actual counts.

---

## Change log

Newest first.

### Presentations failing on a small model

Three faults, all from the same cause. A 4B model asked for a deck produces a
large nested json structure, runs out of output tokens partway through, and emits
a fragment. The loop could not parse it, treated the fragment as a final answer,
and the interface showed an empty box or a line of raw json.

**The loop now tells the difference between prose and a truncation.** A reply
starting with a brace and containing a tool key, which fails to parse, is a
truncation - the loop asks the model to try again and keep it much shorter, up to
twice. Only genuine prose counts as a final answer.

**The prompt now asks for short write arguments** - three or four slides, three
short bullets each - so the truncation is less likely in the first place.

**The pptx tool accepts the shapes a small model actually produces**, not only
the intended one: `title` instead of `heading`, `points` instead of `bullets`,
bullets as a single string, or a slide as plain text. A deck that ends up with no
slides falls back to the subtitle as one summary slide rather than producing a
title slide alone.

Tested against a scripted model that truncates on its first attempt and recovers
on the retry.

### Spreadsheets, session memory, suggestion chips

**Spreadsheets now go to SQLite, never to the vector store.** Added
`structured.py` and `agent/tools_impl/query_data.py`. A question like "how many
breakdowns has P-101 had" is a filter and a count, not a similarity search.
`ingest.py` now routes `.xlsx` files to SQLite and PDFs to Chroma. Added
`make_workbook.py` and a fifteen-row maintenance workbook to the corpus.

The query tool is restricted three ways: only `SELECT` is permitted, the tables a
caller may query are filtered by clearance, and the model is only shown the
schema of tables it may reach. A contractor asking about the workbook is told no
tables are available at their clearance.

**Session memory.** Added `agent/session.py`. The last three turns are kept as
the question plus a one-line gist of the answer, placed at the top of the
transcript. So "why does P-101 keep failing" followed by "what did those cost"
now resolves. Deliberately small — storing whole conversations would grow the
prompt every turn and crowd out the instructions that matter more on a small
model. Cross-session memory remains excluded by design.

**Suggestion chips.** The six-second cycling is gone — it moved while you were
reading it. Starter questions now appear as clickable chips under an empty
composer, alongside your own questions from this session, marked with a dashed
border. Type-ahead with Tab still works and now matches your own history too.
New endpoint `GET /suggestions`.

**A note on the coding model.** `calculate` uses no model at all — it is a regex
check and a restricted `eval`, so arithmetic is exact. The coding model is only
reached for genuine code or query generation, and falls back to the general model
if it is not installed. Worth knowing rather than assuming.

### One file per tool

`agent/tools.py` had grown to 314 lines holding five tool implementations plus
the registry. Split: each tool now lives in its own file under
`agent/tools_impl/`, and `agent/tools.py` is a 73-line registry that says which
tools exist and whether each changes state. Adding a tool is now three steps —
write the file, import it, add a row.

Nothing about behaviour changed. Every tool re-tested after the split, including
the arithmetic guard and the template lookup.

### House templates, longer answers, generated files panel

**Templates from the corpus.** Added `make_templates.py` and three template
documents — approval note, letter, technical report — classified public. Added
`find_template()` to `agent/tools.py`: before a write tool runs, the server
searches for the organisation's template for that document type and gives the
model one further turn to follow its structure. Done in code rather than left to
the model, so it cannot be forgotten. Candidates are scored against the wording
of the request, so "draft an email" reaches the letter template rather than the
approval note, and a missing template returns nothing rather than the nearest
unrelated document.

**Fixed a crash.** `tool_write_pptx` had no `author` parameter while the loop
added one to every write tool's arguments, so every presentation request failed
with `unexpected keyword argument 'author'`. All five tools now accept `author`
and ignore anything unexpected.

**Answers were being cut off mid-sentence.** Passage text raised from 600 to 1200
characters, the transcript fed back to the model from 2200 to 5000, and
`num_predict` set to 1600 so the model is allowed a longer response.

**Answers now finish properly.** The prompt instructs the model to complete its
thought, close with a conclusion or recommendation, and say less about each point
rather than running out of room halfway through.

**Formatting guidance.** Four shapes in the prompt — email or letter, approval
note, report, and plain prose for everything else. Kept deliberately short: on a
small model a long prompt crowds out the instructions that matter more, such as
citing sources and not guessing.

**Model routing was misfiring.** "Report" and "analysis" were matching the coding
keywords, so a presentation request was routed to the coding model and fell back.
The keyword list is now narrow enough to fire only on genuine calculation or code
requests.

**Generated files panel.** New `GET /outputs` endpoint and a fourth tab in the
security rail listing everything written this session, each with a download link.
Refreshes automatically when an approval writes a file.

**MAX_STEPS raised from 6 to 7** to leave room for the extra template turn.

### Registry created
Added `REGISTRY.md`. Cleared stale references across the documentation — the old
`sec_admin` account, the `fake_search` and `fake_ask` stubs, and references to
`index.html`. Deleted the dead stub functions from `server.py` and removed
`oasis_backup.html`.

### Login reads roles from the server
Added `GET /roles`. The login screen now builds its cards from that endpoint
instead of hardcoding them, so adding an account to `policy.yaml` makes it appear
with no HTML change. This fixed a real fault: the page still offered `sec_admin`,
which had been renamed to `admin`, so sign-in failed.

### Presentation tool
Added `write_pptx` to `agent/tools.py`. Produces a deck with a title slide, one
slide per section, and a sources slide listing every document and page the
content came from. Closes a use case the sponsor named explicitly.

### The agent
Added `agent/tools.py` and wrote `agent/loop.py`. Five tools, a capped loop, and
proposal mode. `server.py` `/ask` now runs the agent rather than calling the
model directly; `/approve` executes the proposed action; `/download/{filename}`
serves the result. The interface shows tool steps above each answer and offers
the generated file for download.

### Three roles, and the policy file
Added `policy.yaml` and `policy.py`. Accounts, clearance levels and document
classifications moved out of code. Went from two roles to three — Administrator,
Employee, Contractor — with three hierarchical levels: public, internal,
restricted. Each role retrieves its own level and everything below.

### The documents tab
Added `GET /documents` and `POST /upload`. Administrators can add a document and
classify it from the interface; it indexes immediately and is recorded in the
ledger. Other roles do not see the uploader. An upload joins the searchable
library permanently — unlike an attachment, which is used for one question and
never indexed.

### Real retrieval and real inference
Wrote `ingest.py` and `my_rag.py` properly and replaced `fake_search`. Wrote
`agent/models.py` and replaced `fake_ask`. Both stubs gone from `server.py`.

### The interface
Rebuilt with two themes — mint and lavender on white, near-black and turquoise —
a particle wave background, a centred composer with Tab-to-accept suggestions,
and the security panel moved behind a button so it does not clutter the screen.

### The starting point
`oasis.html`, `server.py` and the five synthetic corpus PDFs, running on
stubs so the interface could be built before retrieval or the model existed.
