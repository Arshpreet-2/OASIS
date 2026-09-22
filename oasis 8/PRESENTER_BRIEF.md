# OASIS — presenter briefing

For someone demonstrating this who has not used it before. Read it once through,
then run the five questions in §7 on the actual machine before you present.

---

## 1. Before you touch anything

Three things must already be true, and none of them are visible from the
interface:

- **Ollama is running** in its own terminal or as the menu-bar app, with
  `qwen3:4b` pulled. Check with `ollama list`.
- **`python3 ingest.py` has been run** in this folder. If it has not, the app
  works perfectly and every answer comes back with **0 passages**. Nothing warns
  you.
- **The server was started from inside the `oasis` folder.** Started from the
  parent folder it runs fine and finds no documents — same symptom.

Sign-in is `admin` / `employee` / `contractor`, password `123` for all three.

---

## 2. Things that look wrong but are correct

**Answers take 20–60 seconds.** A document takes longer — two model calls. The
tag under your question changes as it works: reading the question → searching
the documents → drafting. Talk while it runs; do not stand in silence.

**The phase tag is paced, not measured.** It describes the order the agent works
in. If asked: the real steps appear underneath the answer when it arrives.

**The send button turns into a red stop button** while a question runs. Clicking
it gives you the input back. It does **not** stop the model — Ollama finishes
what it started, so the next question waits a few seconds. Say that if asked;
do not claim it cancels.

**The Ledger is empty for Employee and Contractor** — in fact the menu tab is
not there at all. That is deliberate: the ledger names every person and every
filename, so showing it to a contractor would leak both. Only the Administrator
sees it.

**An answer with no citations is not an error.** A greeting, a calculation and a
spreadsheet answer all legitimately have no sources.

**Files are per chat and per person.** A document you generate appears in the
Files tab of *that chat only*, and only for the person who made it — not even
the Administrator can see someone else's. Click **+ New chat** and the Files tab
is empty, because those files belong to the previous chat. The old chat is still
in the left sidebar and clicking it brings both its messages and its files back.

**"Knowledge from model explicitely"** at the end of an answer, with an amber
bar, means the model answered from its own knowledge rather than the documents.
That only happens if the **Documents + model** toggle is on. It is off by
default and resets on sign-out.

---

## 3. Do NOT try these live

Every one of these will fail or embarrass you. Nothing here is a secret — say so
if asked — but do not discover it on stage.

| Do not | Why |
|---|---|
| **Upload a spreadsheet** in the Documents tab | PDF only. An `.xlsx` is written to the folder and then throws. Spreadsheets are added from the command line. |
| **Upload a scanned PDF** | Rejected — "No text could be extracted." No OCR in this build. |
| **Attach a spreadsheet** to a question | Silently ignored. You get an answer from the plant corpus as though nothing was attached — the worst kind of failure, because it looks fine. |
| **Attach an image and expect vision** | The vision model is not pulled. The request falls back to the text model, which answers about an image it cannot see. |
| **Ask it to run code** | Sandboxed execution is not built. It will write code as prose; it cannot execute anything. |
| **Ask for a chart as Contractor** | Correctly refused — the workbook is `internal`. Fine to show deliberately, confusing if accidental. |
| **Point at "Bytes out", "Blocked" or the clock** in the Sovereignty panel | Those three are placeholder values. **"Model digest" is real** — that is the actual SHA-256 of the loaded model. |
| **Restart the server mid-demo** | The ledger, all chats and all file ownership are in memory. They are gone. |
| **Ask two things at once** | One question at a time. The second waits. |

---

## 4. File formats — what goes where

**Attach to a question (the + button):** `.pdf` (read as a source), `.pptx` /
`.potx` (used as a deck template, and its text is readable), `.png` / `.jpg`
(vision route — not pulled, do not use). **Not** `.xlsx`, **not** `.docx`,
**not** `.txt`.

**Upload to the library (Documents tab):** `.pdf` only, and it must have real
text in it.

**Added from the command line** (`corpus/` + a line in `policy.yaml` +
`python3 ingest.py`): `.pdf` and `.xlsx`.

**Produced by the system:** `.docx`, `.pptx`, `.xlsx`, and `.png` charts.

---

## 5. Bottlenecks, honestly

**The model is the ceiling.** `qwen3:4b` is a 4-billion-parameter model. Facts
and citations are reliable; *interpretation* is thin. "Analyse this sheet" gives
correct numbers and a shallow read of what they mean. Do not promise insight.

**Speed depends entirely on the machine.** Metal-accelerated on an Apple Silicon
Mac. On Windows-on-ARM there is no GPU or NPU support at all — CPU only, several
times slower. Demo on the Mac.

**One file per question.** "Analyse this and chart it" cannot produce both — the
agent returns as soon as it proposes a file. Ask for the chart separately.

**The Documents tab does not scale.** It recounts every chunk in the index on
each load. Fine at nine documents; a thousand would need a document registry and
pagination.

**Everything except the documents themselves is in memory** — ledger, chats,
sessions, file ownership. A restart clears all of it.

**Login is demo-grade.** Three accounts and a password in a YAML file.
Production means SSO and TLS.

---

## 6. If a judge asks something you do not know

Say you do not know and offer to find out. Do not guess — every claim this
system makes is meant to be checkable, and guessing undoes that in one sentence.

Three you will probably get:

**"Could this run in the cloud?"** It could, but the point is that it does not
have to. Some plants have no outbound connectivity, and that is the case this is
built for.

**"How does someone working from home use it?"** Air-gapped means no internet,
not no network. On-site over the plant LAN; remote over the corporate VPN, where
they are indistinguishable from an internal user. The data never leaves the
organisation.

**"What if the model is wrong?"** Two answers. Numbers do not come from the
model — they come from SQL and a calculator. And nothing is written to disk
without a person approving it.

---

## 7. Run these five before you present

Not as a demo — as a check that the machine is working. Ten minutes.

1. As Administrator: *"Why does the seal on P-101 keep failing?"* — expect an
   answer with citations and passages listed.
2. As Contractor: *"What does the HAZOP say about the reflux drum?"* — expect it
   to say it cannot find it, with no HAZOP in the sources.
3. As Employee: *"How many work orders are there for P-101?"* — expect **8**.
4. As Administrator: *"Draft an approval note for replacing the seal on
   P-101."* — expect a proposal, then approve it and open the file.
5. As Administrator: *"What is the vibration limit on compressor K-401?"* —
   expect it to say it does not know.

If any of those five behaves differently, something is wrong with the setup —
almost certainly ingest or the launch folder — and it is better to find out now.
