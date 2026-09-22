# Changelog

---

## v8 — one request, several approvals

### An approved action no longer ends the turn

"Chart the work orders and put them in a deck" used to be two requests: the
loop returned the moment it proposed a file, so the chart was the end of it.
The turn now carries on after an approval - chart, approve, deck, approve,
answer - with the person approving each write. Nothing runs unseen; the agent
simply finishes what it started.

The loop's driving body was extracted so it can be re-entered, and the context
needed to resume is kept alongside the pending action. The step budget carries
across, so a chained request cannot run further than a single one.

### The approval card shows what it is approving

A card reading "agent wants to write a file" is not a check on anything. It now
shows:

- the **SQL** for a chart or a spreadsheet - the part a plant engineer can
  verify at a glance, since wrong SQL is wrong numbers
- the **slides** for a deck, with headings, bullets and which slide carries a
  chart
- the **code** and its container limits for the sandbox, as in v7

This matters more once actions chain. Approving four things in a row from cards
that say nothing is a sequence of clicks, not a sequence of decisions.

### Ledger fix (also applied to v4, v5 and v7)

An administrator saw only the last six entries. Signing out and back in - two
entries of its own - pushed everyone else's activity out of view, so the trail
looked cleared when nothing had been lost. The view is now the last 250.


> v6 was skipped. v7 is v5 plus the correction workflow.

---

## v7 — corrections, dates, sandbox visibility, and decks worth looking at

### Decks

**A house deck template**, `corpus/template_deck.pptx`, classified `public`.
"Make a presentation in the company format" now works for decks the way the
letter and report templates already worked for documents. Built from
`make_deck_template.py`, so the branding can be regenerated rather than
hand-edited.

The design lives in the **slide master and layouts**, not on the template's
own slides. python-pptx builds a deck by adding slides from a template's
layouts and never copies its slides - so a design drawn on slides looks right
in the template and vanishes in everything generated from it. Getting this
wrong is invisible until you open the output.

Two limits of python-pptx had to be worked around: neither a master nor a
layout will accept new shapes, so the furniture is built on a throwaway
presentation and its XML copied into each layout; and paragraph alignment is
inherited from the master's title style, so setting it per layout alone left
every title centred.

**Charts now go in the deck.** `write_chart` already wrote a PNG; a slide can
now name it as `image` and `write_pptx` places it, scaled to fit rather than
stretched, in the body placeholder's space. A deck that shows the numbers
rather than describing them.

Layouts are deliberately the standard ones. A template offering an eight-slot
Timeline produces slides with seven holes in them, because the tool fills a
title and one body - which is what the earlier attached template did.

## v7 — corrections, effective dates, and the sandbox made visible

### Sandbox fixes, found by using it

**Approving code reported "nothing was written".** `approve()` judged every
approved action by whether a file appeared. `run_code` returns output, not a
file, so a successful run was reported as a failed write - and the misleading
turn then poisoned the next one, because the session gist said nothing had
happened and the model stopped reaching for the tool. It now returns the
output as the answer.

**The approval card did not show the code.** A person cannot meaningfully
approve a program they have not been shown, and the container it runs in is the
other half of the claim. Both were invisible. The card now shows the code, the
SQL that feeds it, and the constraints underneath: no network, read-only
filesystem, 512 MB, one CPU, standard library only, killed after 10 seconds.

**Write-tool wording for a tool that writes nothing.** "A document is ready.
Approve to write the file" appeared for code. It now says the code is ready to
run and asks the reader to read it first.

**Asking for code and asking for an answer were the same request.** "Write a
python function to print hello" ran the sandbox. They are now distinguished:
a request for code is answered in the reply, in a fenced block, unrun. The
sandbox is only for a result that cannot be obtained another way - and chart
requests are steered to `write_chart`, which exists and works.

The container itself needed no change. A `ModuleNotFoundError: No module named
'matplotlib'` from a real run was the proof: the isolation held, and the model
had simply written code for a normal machine.

## v7 — corrections, and effective dates

**On GitHub:** not yet. Not model-tested — built after the demo build was
settled.

### Corrections

An answer can be wrong. Until now nothing could be done about it except edit
the corpus by hand.

**Anyone may raise a correction**, whatever their clearance — spotting an error
is not a privileged act. They say what is wrong and what the right answer is.
Nothing changes: it is stored as pending and the ledger records who raised it.

**An administrator reviews it** in a Corrections tab, visible only to them
because it carries other people's questions and answers. They can approve,
reject, or edit the wording and then approve — an engineer may be right about
the fact and clumsy about the phrasing.

**The approver must not be the submitter**, enforced on the server. A control
that exists only in the browser is not a control.

**Approving requires setting a clearance level.** A correction is a document;
an unclassified one in a clearance-filtered store is the hole the whole design
exists to avoid. Corrections are then filtered by clearance like any passage.

**It is stored, not trained.** Deleting the record reverts the system —
which is the argument for this design over fine-tuning: a mistaken correction
is one record removed, where retraining cannot be undone.

**It is cited as a correction**, with the approver's name and date, never
folded into a document citation. The reader must be able to tell a person's
correction from a manual.

### Effective dates

A correction may only override a document it is **newer** than. Otherwise a
correction approved in March would silently outrank a manual revised in June.

So every document now carries an effective date — the date on the document,
not the day it was ingested. Three sources, in order, each recorded:

- **stated** — an administrator typed it. Believed over everything else.
- **document** — read from the text, and only from an unambiguous pattern.
- **default** — 1 July 2026, when neither of the above supplied one.

The Documents tab shows which applied, so a fallback is never mistaken for a
real date.

Extraction is deliberately conservative, because a wrong date that looks
confident is worse than no date. Two rules came out of testing the real corpus:
a revision number is not a date, and **a future date is ignored** — the HAZOP
lists action due dates, and taking the latest date in the text picked one of
those as the report's own.

Of the eight corpus documents, three carry real dates (HAZOP 15 Aug 2026,
inspection report 28 Mar 2026, maintenance log 30 Jun 2026) and five fall back
to the default, marked `(assumed)`.

### Files

New: `registry.py`, `corrections.py`. Changed: `ingest.py`, `structured.py`,
`server.py`, `agent/loop.py`, `oasis.html`.


---

## v5 — sandboxed execution, and formatted answers

**On GitHub:** not yet. **v4 is the tested build** — v5 adds the sandbox, which
needs Docker on the machine and has not been exercised against a real model.

### Added

**`run_code` — Python in a container.** For analysis SQL cannot express: a
trend line, a correlation, a distribution. `--network none`, read-only
filesystem, 512 MB, one CPU, `--cap-drop ALL`, `--user 65534`,
`no-new-privileges`, killed after 10 seconds. The data is handed in as a CSV on
a read-only mount; the corpus, the vector index and the application source are
not in the container, so code cannot reach them however it is written.

`changes_state: True`, so the approval gate already in use applies without
special handling — the model proposes, a person reads the code, then it runs.
Two layers: review, and containment even of an approved mistake.

Docker is optional. Without it the tool says so and the rest of the system is
unaffected.

**Markdown rendering in the answer.** Models write `**bold**` and `- bullets`
whether or not you ask them to, and those were showing as literal characters
with the line breaks collapsed. A small fixed subset is now rendered: bold,
inline code, fenced code blocks with indentation preserved, and bulleted and
numbered lists.

Escaping happens **before** any formatting, so nothing the model writes can
become markup — verified with a script tag in the answer text. Reversing that
order would be an injection hole in a system whose pitch is that it can be
trusted with confidential documents.


---

## v4 — no keyword guessing

**On GitHub:** not yet. **v3 is the known-good build** — keep it until v4 is
tested against the real model.

### Removed

Three regexes in `loop.py` decided what the user meant by matching keywords:

- `HOUSE_FORMAT` — did they want the company template?
- `ATTACHED_FORMAT` — is this attachment a template or a source?
- `REUSES_LAST` — are they reshaping the previous answer?

Measured against 21 realistic phrasings, they matched 4. "Make it look
official", "use the usual layout", "match this", "same style as this file",
"same thing but as a letter", "and as an email?" — all missed, and all fail
**silently**: a confident answer that ignored what was asked. English only, so
any Hindi or mixed-language instruction missed by construction.

Also removed the extra model turn that injected a template after a blind
draft, and `_intended_write`, which guessed which write tool a request was
heading for.

### Instead

Everything now goes into the transcript unconditionally, and the model decides:

- the attachment, announced by name, with **both** its text (in case it is to
  be read, summarised or rewritten) **and** its layouts if it is a deck (in
  case it is to be copied)
- every house template the caller may see, listed rather than selected
- the previous answer in full, with a line saying when it applies

The user's sentence is already in the prompt. Code that guesses from keywords
is a second, much worse reader of the same words.

### What it costs

The first prompt grows from ~4,700 to ~8,600 characters, roughly 1,000 extra
tokens per request. On a 4B model that is real latency. Call count is
unchanged: 2 for a plain question, 2 for a house-format document.

It also moves judgement from regexes onto a 4B model. On the cases the regexes
anticipated, the regexes were right; the model may not be. That is the trade —
predictable failure on anticipated phrasings versus a fair chance on any
phrasing.

**Test both builds on the real model before choosing.**


---

## v3 — charts

**On GitHub:** not yet

### Added

**`write_chart` — charts from spreadsheet data.** `agent/tools_impl/write_chart.py`,
plus one row in the registry. The model supplies SQL and a chart type; the tool
runs it through `run_query`, so clearance is inherited — a table above the
caller's level cannot be charted any more than it can be read. `changes_state:
True`, so it is proposed and waits for approval like any other file. bar, line,
pie and barh. Values are printed on every bar, because a chart nobody can read a
value off is a picture, not a finding.

Approved charts render inline under the answer and as thumbnails in the Files
tab. matplotlib runs headless (`Agg`), set before importing pyplot.

Refuses rather than rendering nonsense: one column, text in the number column,
an empty result, more than 25 rows, an unknown chart type, a non-SELECT.

`matplotlib` added to `requirements.txt`. New dependency — re-run
`pip install -r requirements.txt`.

**Known limit:** charts are standalone PNGs. They are not yet embedded into the
generated .docx or .pptx.

### Fixed

**The Files panel showed a stale list.** Approving a file never refreshed it, so
a second document appeared only if the tab was reopened. `oasis.html`.

**"Put the above report in the company format" searched the library again.** The
content was already on screen, but session memory kept only a 160-character
gist, so the model had to rediscover it - a whole model call returning the same
passages. The previous answer is now kept in full and supplied when the request
is a reshape ("reformat that", "turn the above into a letter", "put that in the
company format"). Saves one call and stops the content drifting between
versions. `agent/session.py`, `agent/loop.py`.

**Landing subtitle reworded.** It promised documents-only answers, which stopped
being true when the model-knowledge toggle and attachments arrived.

### Faster documents

**The house template is now fetched before the first draft, not after it.** The
loop used to let the model draft blind, then inject the template and make it
write the whole document a second time - two long generations per request. When
a house format is asked for, the template goes into the first prompt instead. A
house-format document is now **2 model calls, down from 4**.

### PowerPoint templates

Attach a `.pptx` or `.potx` and the deck is built inside it. python-pptx opens
the file and inherits the master, so fonts, colours, placeholder positions and
the logo are exact rather than approximated - far better than describing a
layout to the model in words, and it costs no extra model turn because the
layout is never the model's problem.

Layouts are chosen by name first ("Title Slide", "Title and Content") and by
placeholder shape as a fallback, never by index - templates do not agree on
order. A template that cannot be used falls back to the house layout rather
than failing.

### Fixed after first use

**"Plot downtime over time" returned "None written."** Two bugs stacked. The
loop injects `user_level` on the read-only tool path but not on the write path,
so `write_chart` - which reads the tables - defaulted to `public` and was
refused. Then `approve()` built its message as `f"{result.get('file')} written."`
without checking whether the tool had actually succeeded, so a clearance
refusal came back looking like a write with a `None` filename.

Both fixed: the caller's clearance now reaches `write_chart` (supplied by the
loop, never by the model - a model that could name its own clearance could
raise it), and `approve()` surfaces the tool's error instead of reporting
success.

### The model chooses the slide layouts

The first version matched layout names against a hardcoded list - "Title
Slide", "Title and Content". A real template with layouts called Intro, Agenda,
Chart, Quote, Timeline and Summary defeated it completely: it picked "Section
Break" (a picture layout) for the title and put everything else on "Content 2
Column", using 2 of 13 layouts and both wrongly. No amount of extra names fixes
that - the next template names things differently again.

The template's layouts are now profiled at attach time - name and content slots
for each - and put into the prompt the way the table schema already is for
query_data. The model names a layout per slide, and the tool matches by name
with the old heuristic as the fallback. Nothing in the code knows what any
layout is called, so a template using Opener / Two-up / Closer works the same.

Same principle as the routing eval: do not encode the decision, supply the
information and let it be made where the context is.

### Exploring a sheet

**`describe_table` - profile a spreadsheet in one call.** The model is given
column NAMES in its prompt but nothing about the values, so "analyse the
maintenance sheet" left it guessing what was worth querying, and a small model
guessing costs turns. One call now returns row count, and per column its type,
distinct count, range for numbers and dates, and the commonest categories.

Column kinds are inferred from the data, not the schema - SQLite is loosely
typed and spreadsheets arrive as text. A date column is shown as a range rather
than fifteen one-off categories, and a column with one distinct value per row is
marked an identifier rather than listed out.

Read-only, clearance inherited through the same path as `query_data` - the shape
of a table is information about its contents.

### Documents tab

**Spreadsheets are now listed.** `maintenance_workbook.xlsx` was invisible
because that tab lists the vector index and spreadsheets live in SQLite. It is
now shown alongside the documents, marked **table** with a row count rather than
a chunk count, so the difference is visible rather than looking like a file that
failed to index.

**The listing is now filtered by clearance.** It previously showed every
filename to every role, including restricted ones. A contractor could learn
that `hazop_report.pdf` exists without being able to read it - the same
existence disclosure the ledger was gated for. Spreadsheets were already
filtered, so the tab was inconsistent with itself.

### Files changed from v2

`agent/tools_impl/write_chart.py` (new), `agent/tools.py`, `agent/loop.py`
(one prompt line), `oasis.html` (inline image and thumbnails),
`requirements.txt`, `TEST_CASES.md`, `agent/tests/test_agent.py`.


Version numbering starts at v2 — v1 is the merged build pushed to GitHub.
Each entry says what changed and whether it has reached the repo.

---

## v2 — merged agent, bug fixes, chats and access control

**On GitHub:** not yet

Files changed from v1: `agent/models.py`, `agent/loop.py`, `TEST_CASES.md`
(new), `.gitignore`, plus two deletions.

### Fixed

**Routing matched against the system prompt.** `loop.py` passed the whole
transcript to `ask_model`, and the transcript contains the SYSTEM prompt, which
mentions "calculate", "python" and "sql" in the tool instructions. Every request
therefore routed to the coding model. Added a `route_on` parameter so routing
looks at the user's question. `agent/models.py`, `agent/loop.py`.

**JSON taken from inside the model's reasoning.** `qwen3:4b` reasons out loud
and often writes a tool name in JSON form while rejecting it. `_json_from` took
the first `{...}` in the reply, so the rejected call ran instead of the real
one — wrong tool, zero passages, no approval note. Added `_strip_reasoning` to
remove `<think>` blocks, and `_json_from` now returns the **last** object
carrying a `tool` or `answer` key. `agent/loop.py`.

**Generation budget too small for the template turn.** A reasoning model spends
tokens thinking before it emits any content, drawn from the same `num_predict`
budget. The template turn — regenerate a whole document to a house format — is
the longest deliberation, and at 1600 it ran dry and returned empty content.
Raised to `num_predict: 6000`, `num_ctx: 16384` (Ollama defaults to 4096).
`agent/models.py`.

**Empty replies treated as answers.** An empty string fell through to `_finish`
and became a blank response. The loop now retries, with an instruction not to
reason step by step. `agent/loop.py`.

### Reverted

**`think=False` was sent to Ollama and then removed.** With `think` omitted,
Ollama returns reasoning and reply together in `message.content`, which
`_strip_reasoning` handles. Passing `think=False` switches Ollama to split
output — reasoning into `message.thinking`, `content` empty — which the loop
read as "no answer". qwen3 reasons either way, so the parameter bought nothing
and cost the reply. `SEND_THINK = False` remains as a named constant with the
reasoning written out, so nobody re-adds it.

### Added

`TEST_CASES.md` — 66 cases across 13 sections, with real ground truth from the
corpus and the workbook. Every case marked READY, NEEDS MODEL or NOT BUILT.

### Removed

`diag_turn2.py` (throwaway debug script), `data.db` (build artifact, now in
`.gitignore`).

---

## v1 — merged build

**On GitHub:** yes, as branch `merge-agent`

The merge of the two agent layers. Sushil's multi-step loop, tool registry,
approval gate, clearance propagation, citations and session memory; Aditi's
`config.py`, base64 image encoding, vision model choice and test cases.
`planner.py` dropped. Renamed to OASIS. See `OWNERSHIP.md` for the reasoning
behind each decision.

---

## Still not built

Unchanged since v1. See `TEST_CASES.md` §10 for detail.

- Sandboxed code execution — Aditi
- OCR for scans and drawings — Aditi
- Chart generation from spreadsheet data
- Analysis of a single attached document in isolation
- Sensitivity classification on upload
- Real egress counters
