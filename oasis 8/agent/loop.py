"""
THE AGENT LOOP.

    plan -> call a tool -> observe the result -> decide -> repeat

Capped at MAX_STEPS so it cannot run forever.

PROPOSAL MODE. Read-only tools run freely. Anything that changes state is never
executed by the agent - it finishes reasoning, states what it intends to do, and
waits for a person to approve. That is what makes an agent acceptable in a plant.
"""

import json
import re

from agent.models import ask_model
from agent.session import recall, last_answer  # remember() is server.py's
from agent.tools import TOOLS, catalogue
from agent.tools_impl.templates import available_templates

# Shown on the approval card. A person approving code must be able to see
# both what it is and what it can reach - the second is the whole security
# claim, and it was invisible.
SANDBOX_LIMITS = ("no network · read-only filesystem · 512 MB · 1 CPU · "
                  "standard library only · killed after 10s")

MAX_STEPS = 7          # small models wander; keep the leash short


MAX_RETRIES = 2        # attempts to recover from truncated json
PENDING = {}           # action_id -> everything needed to run it later


GROUNDING = {

"documents": """- Answer ONLY from passages the search returned. If they do not contain the
  answer, say so plainly. Never use your own knowledge about equipment.
- If the question is not about this plant at all - a greeting, or small talk -
  reply in one short friendly line. Do not refuse it in document language.""",

"assisted": """- Answer about the plant ONLY from passages the search returned. Its
  equipment, settings, procedures, costs and records must come from the
  documents or not at all - never from your own knowledge, however confident.
- A greeting or small talk is not a question. Reply in one short friendly line.
  Do not search, do not mention documents, and do not mark it.
- If the passages do not answer a plant question, say so plainly first. You may
  then add general background from your own knowledge. Whenever you do, END the
  whole answer with this line, on its own, with nothing after it:
  (Knowledge from model explicitly)
  The caveat goes last. A reader should get the answer before the disclaimer,
  not a disclaimer before they have read a word.
- For a substantive general question that is not about this plant - what
  cavitation is, how a mechanical seal works, what an API standard covers -
  answer from your own knowledge and end with that same line. Do not cite
  documents for it.
- Add that closing line only when you are actually stating facts from your own
  knowledge. Never add it to a greeting, an apology, a clarifying question, or
  a refusal.
- Answer the question and stop. Do not comment on how the user phrased it, do
  not advise them on their word choice, and do not add asides about what they
  should or should not have said. You are a plant tool, not a tutor.""",
}


REUSE_NOTE = """
Your previous answer in this chat, in full. If the request refers to it -
reshaping it, reformatting it, turning it into a document - work from this
rather than searching again. If the request is a new question, ignore it.
--- previous answer ---
{answer}
--- end previous answer ---

Keep any citations it already carries.
"""




ATTACHED_HEADER = """
The user attached a file to this question: {name}
Everything below describes it. What to DO with it is in their request - they
may want it read, summarised, checked against the documents, used as the shape
for something new, or rewritten. Decide from what they asked.
"""

ATTACHED_TEXT = """
--- text of {name} ---
{text}
--- end of {name} ---
Cite it like any document, as [{name} p.1]. It is not indexed, so
search_documents will not return it.
"""

CORRECTIONS_NOTE = """
A person has reviewed and approved the following corrections. Each is a
human-verified fact that OUTRANKS the documents on the point it covers,
because it is newer than the document it corrects.

{corrections}

Where a correction contradicts a passage, follow the correction and say
plainly that the document is out of date on that point. Cite it as
[correction approved by <name> on <date>] - never fold it silently into a
document citation, because the reader must be able to tell a person's
correction from a manual.
"""

HOUSE_NOTE = """
The organisation's own templates, available if the request calls for one:

{templates}

Use one only if the request asks for the house, company or standard format, or
implies it. Otherwise write in the plain shape described in the rules above.
When you do use one, follow its headings and order.
"""

LAYOUTS_NOTE = """
The user attached {name} as the deck template. These are its layouts:

{layouts}

When you call write_pptx, name a layout for each slide with a "layout" field,
and optionally "title_layout" and "sources_layout" for the opening and closing
slides. Choose by what each layout is for - its name and its slots say so. A
layout with a picture slot needs an image you do not have, so prefer one
without unless the slide is a divider. Use a name exactly as written above; if
none fits, leave "layout" out and a sensible default is used.
"""

ATTACHED_NOTE = """
The user attached a document to this question. Its full text is below. Treat it
as a source alongside the plant's own documents, and cite it by name the same
way, like [{name} p.1]. It is not in the document store, so search_documents
will not return it.

--- attached: {name} ---
{text}
--- end attached ---
"""

SYSTEM = """You are an assistant working inside a refinery's own document system.

You may call these tools, one at a time:

{tools}

Reply with ONE json object and nothing else:

  {{"tool": "<name>", "args": {{...}}}}          to call a tool
  {{"answer": "<your answer>"}}                  when you are finished

Rules you must follow:
- Call search_documents before answering anything about the plant.
{grounding}
- Use calculate for arithmetic. Never compute in your head.
- Use query_data for anything counted, totalled or averaged over the tables
  listed below. Never search for a number that a query would answer exactly.
- An attached file may be a source to read, a shape to copy, or something to
  rewrite. The request says which. A deck attached as a template is passed to
  write_pptx with a "layout" named per slide; a deck attached to be summarised
  is read from its text above.
- When asked to analyse, explore or summarise a spreadsheet, call
  describe_table FIRST to see what is in it, then query_data two or three times
  for the patterns that profile suggests, then write up what you found. Do not
  guess what is worth querying.
- Asking FOR code and asking for an ANSWER are different requests. "Write a
  python function to do X", "show me a regex", "give me the SQL" want the code
  itself: write it in your reply, in a fenced block, and do NOT run it. Nobody
  asked you to execute anything.
- Use run_code only when the user wants a RESULT you cannot obtain any other
  way - a trend, a correlation, a distribution, a forecast over many rows.
  Counting, totalling and averaging belong to query_data; drawing a chart
  belongs to write_chart. The sandbox has no network and only the standard
  library - no pandas, no numpy, no matplotlib - and a person reads the code
  before it runs.
- A chart belongs IN the deck. If you have written one with write_chart, name
  its filename as the "image" field of a slide, instead of describing the
  numbers in bullets. A slide carrying a chart needs no bullets.
- Use write_chart when the user asks to see, plot, chart or graph tabular data,
  or when a comparison across categories or a trend over time is the point. The
  SELECT must return exactly two columns: the label first, the number second.
- Do not open with a greeting or the person's name. They asked a question;
  answer it. Use their name only if they greeted you first.
- A question about a general concept - what distillation is, how a seal works,
  what an API standard covers - is not a question about this plant. Answer it
  from your own knowledge without searching. Search when the question names
  equipment, a tag, a procedure, a cost or a record.
- Give the answer room. Where the passages support it, explain in a few
  sentences or a short paragraph rather than one line, and say why, not only
  what. Do not pad a thin answer to fill space.
- Cite the document and page for each claim, like [pump_manual_p101.pdf p.88].
- When asked to produce a document, presentation or spreadsheet, call the write
  tool. It will not run immediately - a person will be asked to approve it.
- Keep the arguments to a write tool SHORT. A presentation is three or four
  slides with three short bullets each, never more. A document is a few short
  paragraphs. Long arguments get truncated and the call is wasted.

Finishing:
- Always complete your thought. Never stop mid-sentence.
- Close with a conclusion or a recommendation, not a trailing fragment.
- If there is more to say than fits, say less about each point rather than
  running out of room halfway through.

Shape your writing to what was asked:
- EMAIL or LETTER - a subject line, a greeting, two or three short paragraphs, a
  clear recommendation, and a sign-off.
- APPROVAL NOTE - what was found, what caused it, what is recommended, what it
  costs or how long it takes, then a line requesting sign-off.
- REPORT - a heading, then short sections. Findings before conclusions.
- ANYTHING ELSE - plain prose. Do not impose headings on a simple answer.

Tables you may query with query_data:
{schema}
"""


TEMPLATE_NOTE = """
The organisation's own template for this kind of document was found in the
library ({doc}). Follow its structure and section order. Its content is an
example only - use the facts from the passages above, not from the template.

--- template ---
{text}
--- end template ---
"""


THINK = re.compile(r"<think>.*?</think>|<thinking>.*?</thinking>",
                   re.DOTALL | re.IGNORECASE)


def _strip_reasoning(text: str) -> str:
    """Remove a reasoning model's thinking block.

    qwen3 and similar emit <think>...</think> before the real reply, and that
    block often mentions a tool in json-ish form while considering and
    rejecting it. Parsing before stripping picks up the rejected call instead
    of the real one. An unclosed block means the reply was truncated mid-think,
    so there is no usable json after it either.
    """
    if not text:
        return ""
    text = THINK.sub("", text)
    low = text.lower()
    for tag in ("<think>", "<thinking>"):
        if tag in low:
            text = text[:low.index(tag)]
            low = text.lower()
    return text.strip()


def _looks_like_json(text: str) -> bool:
    """Did the model try to emit json and fail? A fragment starts with a brace
    and a tool key but never closes. That is a truncation, not an answer."""
    t = _strip_reasoning(text)
    t = re.sub(r"^```(?:json)?", "", t, flags=re.M).strip()
    return t.startswith("{") and ('"tool"' in t or '"answer"' in t)


def _json_from(text: str):
    """Small models wrap json in prose or fences. Dig it out.

    Takes the LAST object carrying a "tool" or "answer" key, not the first.
    A model that talks through its options leaves earlier objects behind; the
    decision it settled on is the final one.
    """
    if not text:
        return None
    text = _strip_reasoning(text)
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    found = []
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(text[start:i + 1])
                    if isinstance(obj, dict):
                        found.append(obj)
                except Exception:
                    pass
                start = None

    for obj in reversed(found):
        if "tool" in obj or "answer" in obj:
            return obj
    return found[-1] if found else None


def run_agent(question: str, user: str, user_level: str,
              user_name: str = "", images: list = None,
              token: str = "", mode: str = "documents",
              attached: dict = None) -> dict:
    """Returns the standard response dict. Never raises.

    mode: "documents" (default) answers only from the indexed corpus.
          "assisted" additionally allows the model's own general knowledge,
          but never for this plant's equipment, settings or records, and only
          when explicitly labelled so the reader can tell the two apart.
    """
    steps, sources, model_used, model_reason = [], [], "", ""
    retries = 0
    budget = MAX_STEPS
    attempted = set()     # (tool, args) already tried, to catch loops
    from structured import schema
    tables = schema(user_level) or "  (none available at your clearance)"

    if mode not in GROUNDING:
        mode = "documents"
    transcript = SYSTEM.format(tools=catalogue(), schema=tables,
                               grounding=GROUNDING[mode])
    # Everything about the attachment, the templates and the last answer goes
    # into the transcript. Nothing here decides what the user MEANT - the
    # user's sentence is already in the prompt, and code that guesses from
    # keywords is a second, much worse reader of the same words. Measured: of
    # 21 realistic phrasings the three regexes this replaced matched 4.

    if attached:
        transcript += ATTACHED_HEADER.format(name=attached["name"])
        if attached.get("text", "").strip():
            transcript += ATTACHED_TEXT.format(name=attached["name"],
                                               text=attached["text"][:12000])
        if attached.get("template_path"):
            try:
                from agent.tools_impl.write_pptx import (profile_layouts,
                                                         layouts_for_prompt)
                transcript += LAYOUTS_NOTE.format(
                    name=attached["name"],
                    layouts=layouts_for_prompt(
                        profile_layouts(attached["template_path"])))
            except Exception:
                pass

    # Approved corrections that still hold, at this clearance. They go in
    # before the passages, so the model reads the human-verified fact first.
    try:
        import corrections as _cor
        found = _cor.relevant(question, user_level)
        if found:
            lines = []
            for item in found:
                c = item["correction"]
                lines.append(
                    f'- On "{c["question"]}": {c["correct_answer"]}\n'
                    f'  (approved by {c["approved_by"]} on '
                    f'{(c["approved_at"] or "")[:10]}'
                    + (f', corrects {c["corrects"]}' if c.get("corrects") else "")
                    + ")")
            transcript += CORRECTIONS_NOTE.format(
                corrections="\n".join(lines))
            steps.append({"tool": "corrections",
                          "result": f"{len(found)} approved correction"
                                    f"{'s' if len(found) != 1 else ''} apply"})
    except Exception:
        pass

    house = available_templates(user_level)
    if house:
        transcript += HOUSE_NOTE.format(
            templates="\n\n".join(
                f'--- {t["document"]} ---\n{t["text"][:1800]}' for t in house))

    previous = last_answer(token)
    if previous:
        transcript += REUSE_NOTE.format(answer=previous[:6000])

    history = recall(token)
    if history:
        transcript += "\n" + history
    transcript += f"\nRequest from {user_name or user}: {question}\n"

    return _drive(transcript, steps, sources, attempted, budget,
                  question, token, user_level, user_name, images,
                  model_used, model_reason, user, attached)


def _drive(transcript, steps, sources, attempted, budget,
           question, token, user_level, user_name, images,
           model_used="", model_reason="", user="", attached=None):
    """The agent's turn, from wherever it has got to.

    Separated out so an approved action can carry on rather than end the
    request. Before this, "chart the work orders and put them in a deck" took
    two goes: the loop returned the moment it proposed a file.
    """
    retries = 0
    for _ in range(budget):
        reply, model_used, model_reason = ask_model(transcript, images=images,
                                                    route_on=question)
        images = None                      # only attach on the first pass
        move = _json_from(reply)

        if move is None:
            # An empty reply is not an answer. Reasoning models can burn the
            # whole token budget thinking and return nothing; ask again.
            if not (reply or "").strip() and retries < MAX_RETRIES:
                retries += 1
                transcript += ("\nYou replied with nothing - you spent your "
                               "whole reply thinking. Do NOT reason step by "
                               "step. Output ONE json object immediately, as "
                               "the very first characters of your reply, and "
                               "keep every string short.\n")
                continue

            # Broken json means the model was cut off mid-structure. Ask again,
            # smaller. Only genuine prose counts as a final answer.
            if _looks_like_json(reply) and retries < MAX_RETRIES:
                retries += 1
                transcript += (
                    "\nThat json was incomplete - you ran out of room. Reply "
                    "again with ONE complete json object. Keep it much shorter: "
                    "at most three slides or sections, at most three short "
                    "bullets each, no long strings.\n")
                continue

            # Retries exhausted and it is still broken json. Showing the reader
            # a half-written tool call is worse than saying it failed - they
            # cannot act on it, and it looks like the system is inside out.
            if _looks_like_json(reply):
                return _finish(
                    "I could not complete that. The document I was building "
                    "came out malformed. Try asking for something shorter - "
                    "fewer slides, or fewer sections.",
                    steps, sources, model_used, model_reason)

            return _finish(reply.strip(), steps, sources, model_used, model_reason)

        if "answer" in move and "tool" not in move:
            return _finish(str(move["answer"]), steps, sources,
                           model_used, model_reason)

        name = move.get("tool")
        args = move.get("args") or {}
        spec = TOOLS.get(name)

        if not spec:
            transcript += (f"\nThat tool does not exist. Choose one of: "
                           f"{', '.join(TOOLS)}.\n")
            continue

        # --- state-changing: propose, do not run
        if spec["changes_state"]:
            # Look for the organisation's template for this document type and
            # give the model one more turn to follow it. Done in code so it
            action_id = f"act_{len(PENDING) + 1}"
            args.setdefault("author", user_name)
            # write_chart reads the tables, so it needs the caller's clearance
            # like any other reader. The model never supplies it - a model that
            # could name its own clearance could raise it.
            # Both of these read the tables, so they need the caller's
            # clearance like any other reader. The model never supplies it - a
            # model that could name its own clearance could raise it.
            if name in ("write_chart", "run_code"):
                args["user_level"] = user_level
            if name == "write_pptx" and attached and attached.get("template_path"):
                args["template_path"] = attached["template_path"]
            if name in ("write_docx", "write_pptx"):
                # A deck is a deliverable people read and forward. It cites
                # its sources like every other answer - only write_docx did.
                args.setdefault("sources", sources)
            # Everything needed to carry on afterwards. An approval used to
            # end the turn, so "chart it and put it in a deck" was two
            # requests. Keeping the context here lets one request run to the
            # end, with a person approving each step along the way.
            PENDING[action_id] = {
                "tool": name, "args": args, "user": user,
                "resume": {"transcript": transcript, "steps": steps,
                           "sources": sources, "attempted": attempted,
                           "model_used": model_used,
                           "model_reason": model_reason,
                           "question": question, "token": token,
                           "user_level": user_level, "user_name": user_name,
                           "images": images, "budget": budget - 1,
                           "user": user, "attached": attached},
            }
            steps.append({"tool": name,
                          "result": "awaiting approval"
                                    + (" · sandboxed container"
                                       if name == "run_code" else "")})
            return {
                "answer": (_code_summary(args) if name == "run_code"
                           else _draft_summary(args, sources)),
                "sources": sources,
                "steps": steps,
                "pending_action": dict(
                    {"tool": name, "id": action_id,
                     "description": spec["describe"](args)},
                    **_preview(name, args)),
                "model_used": model_used, "model_reason": model_reason,
            }

        # --- read-only: run it
        if name == "search_documents":
            args = {"question": args.get("question") or question,
                    "user_level": user_level}
        elif name == "query_data":
            args = {"sql": args.get("sql", ""), "user_level": user_level}
        elif name == "describe_table":
            args = {"table": args.get("table", ""), "user_level": user_level}
        # A model that cannot answer will often try the same call again rather
        # than say so. Seven identical searches is not persistence, it is a
        # loop - and it burns the step limit to arrive somewhere worse than
        # "the documents available to you do not contain this".
        signature = (name, json.dumps(args, sort_keys=True, default=str))
        if signature in attempted:
            transcript += (
                f"\nYou already called {name} with exactly those arguments and "
                f"the result is above. Calling it again returns the same thing. "
                f"Either answer from what you have, or say plainly that the "
                f"documents available to this user do not contain it.\n")
            steps.append({"tool": name, "result": "repeated - skipped"})
            continue
        attempted.add(signature)

        try:
            result = spec["fn"](**args)
        except Exception as e:
            result = {"error": str(e)}

        if name == "search_documents":
            for p in result.get("passages", []):
                key = (p["document"], p["page"])
                if key not in {(s["document"], s["page"]) for s in sources}:
                    sources.append({"document": p["document"], "page": p["page"]})

        step = {"tool": name, "result": _short(result)}
        # Carry the withheld count as structured data. The result string is
        # truncated for display, so it cannot be re-parsed downstream.
        if isinstance(result, dict) and "excluded" in result:
            step["excluded"] = result["excluded"]
        steps.append(step)
        transcript += (f"\nYou called {name}. Result:\n"
                       f"{json.dumps(result)[:5000]}\n"
                       f"Now reply with the next json object.\n")

    return _finish("I could not complete that within the step limit.",
                   steps, sources, model_used, model_reason)


def approve(action_id: str, approved: bool) -> dict:
    """Run a proposed action, or discard it."""
    item = PENDING.pop(action_id, None)
    if not item:
        return {"ok": False, "message": "That action is no longer pending."}
    if not approved:
        return {"ok": True, "written": False,
                "message": "Rejected - nothing was written."}

    spec = TOOLS[item["tool"]]
    try:
        result = spec["fn"](**item["args"])
    except Exception as e:
        return {"ok": False, "message": f"Could not complete that: {e}"}

    # run_code produces output, not a document. Judging every approved action
    # by whether a file appeared reported a successful run as a failed write -
    # and the misleading turn then poisoned the next one, because the session
    # gist said nothing had happened.
    resume = item.get("resume")

    def carry_on(note, outcome):
        """Feed the outcome back and let the turn continue.

        Without this an approval was the end of the request, so a chart and a
        deck were two separate asks. The person still approves each write -
        nothing runs unseen - but the agent finishes what it started.
        """
        if not resume or resume.get("budget", 0) <= 0:
            return None
        r = dict(resume)
        r["transcript"] += f"\n{note}\n"
        prior = list(r["steps"])
        if prior and prior[-1].get("result", "").startswith("awaiting"):
            prior[-1] = {"tool": item["tool"], "result": outcome}
        else:
            prior.append({"tool": item["tool"], "result": outcome})
        r["steps"] = prior
        try:
            return _drive(r["transcript"], r["steps"], r["sources"],
                          r["attempted"], r["budget"], r["question"],
                          r["token"], r["user_level"], r["user_name"],
                          r["images"], r["model_used"], r["model_reason"],
                          r.get("user", ""), r.get("attached"))
        except Exception:
            return None

    if item["tool"] == "run_code":
        if not isinstance(result, dict) or result.get("error"):
            return {"ok": False, "written": False, "ran": True,
                    "message": (result.get("error") if isinstance(result, dict)
                                else "The code produced nothing."),
                    "sandbox": SANDBOX_LIMITS}
        out = (result.get("stdout") or "").strip()
        more = carry_on(f"The code was approved and ran. Its output:\n{out}",
                        "ran in the sandbox")
        return {"ok": True, "written": False, "ran": True,
                "stdout": out, "sandbox": SANDBOX_LIMITS,
                "message": out or "The code ran and printed nothing.",
                "continued": more}

    if not isinstance(result, dict) or result.get("error") or not result.get("file"):
        # A refusal is not a write. Reporting "None written." hid a clearance
        # error behind what looked like success.
        return {"ok": False, "written": False,
                "message": (result.get("error") if isinstance(result, dict)
                            else "The tool returned nothing.")
                           or "Nothing was written."}

    more = carry_on(
        f"{result['file']} was approved and written. Continue if the request "
        f"is not yet complete - for instance a chart you have just written can "
        f"now be placed in a deck. If it is complete, answer.",
        f"{result['file']} written")
    return {"ok": True, "written": True, "file": result.get("file"),
            "message": result.get("message") or f"{result['file']} written.",
            "continued": more}


# ---------------------------------------------------------------- helpers

def _finish(answer, steps, sources, model_used, model_reason):
    return {"answer": answer, "sources": sources, "steps": steps,
            "pending_action": None,
            "model_used": model_used, "model_reason": model_reason}


def _preview(name, args):
    """What the person is actually approving.

    A card reading "agent wants to write a file" is not a check on anything.
    The SQL is the part a plant engineer can verify at a glance - wrong SQL is
    wrong numbers - and a deck should show its slides before it is written.
    """
    if name == "run_code":
        return {"code": args.get("code", ""), "sql": args.get("sql", ""),
                "sandbox": SANDBOX_LIMITS}
    if name == "write_chart":
        return {"sql": args.get("sql", ""),
                "chart_type": args.get("chart_type", ""),
                "preview_image": args.get("_preview_file", "")}
    if name == "write_pptx":
        return {"slides": [
            {"heading": sl.get("heading", ""),
             "bullets": sl.get("bullets", [])[:4],
             "image": sl.get("image", "")}
            for sl in (args.get("slides") or [])[:8]]}
    if name == "write_xlsx":
        return {"sql": args.get("sql", "")}
    return {}


def _code_summary(args):
    """What the reader sees while the code waits for approval. Nothing is
    written by this tool, so the write-tool wording was simply wrong."""
    what = "Python is ready to run in the sandbox. Read it, then approve."
    if args.get("sql"):
        what += "\n\nIt will be given the rows from:\n" + args["sql"].strip()
    return what


def _draft_summary(args, sources):
    body = (args.get("body") or "").strip()
    head = args.get("title") or "Document"
    if body:
        preview = body if len(body) < 700 else body[:700] + " ..."
        return f"{head}\n\n{preview}"
    return f"A {head.lower()} is ready. Approve to write the file."


def _short(result):
    s = json.dumps(result)
    return s if len(s) < 220 else s[:220] + " ..."
