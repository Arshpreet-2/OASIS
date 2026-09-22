# Who builds what — OASIS

| File | Owner | Status |
|------|-------|--------|
| `oasis.html` | Sushil | done |
| `server.py` | Sushil | done |
| `policy.yaml` / `policy.py` | Sushil | done |
| `ingest.py` / `my_rag.py` / `structured.py` | Sushil | done |
| `agent/config.py` | **Aditi** | done — model set lives here, incl. her `qwen2.5-coder:3b` |
| `agent/models.py` | Sushil + **Aditi** | merged: config and base64 image encoding from Aditi |
| `agent/tools.py` + `agent/tools_impl/` | Sushil | done |
| `agent/loop.py` | Sushil | done |
| `agent/session.py` | Sushil | done |
| `agent/tests/test_agent.py` | **Aditi** + Sushil | Aditi's 3 cases, plus clearance and approval |
| **Sandboxed code execution** | **Aditi** | NOT BUILT |
| **OCR for scans and drawings** | **Aditi** | NOT BUILT |
| Firewall rules, real egress counters | Sushil | NOT BUILT |

## Merge decisions, and why

Both of us built an agent layer while the other was working. This is what we
kept from each, and the reason in one line.

**Aditi's `config.py` — kept.** Model names belong outside the logic. One file
to edit when swapping a model.

**Aditi's base64 image encoding — kept.** Reads the file and encodes it
explicitly rather than handing Ollama a path and trusting it to read it.

**Aditi's vision model `qwen3-vl:4b` — kept.** Newer than `qwen2.5vl:3b` and the
only one either of us has actually run against a real image.

**Aditi's coder model `qwen2.5-coder:3b` — kept.** The problem statement asks for
code generation, so judges may probe it directly. It is not yet executed anywhere
- that arrives with the sandbox - but a specialist model answering a code question
is better than a generalist, and `ask_model` falls back to the general model if it
is not pulled on the machine.

**Aditi's test cases — kept**, rewritten as assertions and extended with five more:
code generation (output must compile), fallback when a model is missing, grounded
retrieval, clearance separation, and the approval gate.

**Aditi's `planner.py` — dropped.** It spent one model call per request to return
one word, and `ask_model` then routed again by keyword anyway. Measured on a
stubbed Ollama: half of all model calls were this. Removing it cuts roughly a
third off latency on simple questions with no loss of capability.

**Aditi's `loop.py` and `tools.py` — not used.** The loop had to carry the
approval gate, `user_level` propagation to `my_rag.search`, citations and the
step trace, because the frontend and the acceptance criteria depend on all four.
Her single-pass loop had none of them.

**Sushil's `CODE_HINTS` over Aditi's keyword list.** Hers fires on "function",
"sum", "average" and "formula", which appear constantly in ordinary plant
questions. Narrow is safer than broad here.

**Sushil's model fallback — kept.** If a routed model is not pulled, fall back to
the general model. Aditi's version returned the raw exception string into the
chat pane, which looks like a working answer to anyone not reading closely.

## What is left

**Sandboxed code execution (Aditi).** One of the sponsor's four acceptance
demonstrations. Docker, `--network none`, read-only mounts, memory and wall-clock
caps, registered in `agent/tools.py` with `changes_state: True` so it routes
through the approval gate.

**OCR (Aditi).** `/upload` rejects every scanned document today with "No text
could be extracted." Scanned manuals and P&ID drawings are named in the problem
statement.

**Real egress numbers (Sushil).** The sovereignty panel shows fixed values.
Default-deny firewall rules with logging, and `/status` reading the real counts.

## The contract

A tool is a function in `agent/tools_impl/` returning a JSON-serialisable dict,
plus one row in the `TOOLS` registry in `agent/tools.py` with `changes_state`
set correctly. Nothing else in the system changes.

Anything touching documents takes `user_level` and goes through
`my_rag.search`. Never around it.
