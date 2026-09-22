"""
MODEL LAYER - talks to Ollama running locally. No cloud, no external calls.

    ask_model(prompt, images=None) -> (answer, model_used, model_reason)

Routing is deterministic - plain if statements, never another model deciding.
Model names live in agent/config.py (Aditi), never typed into the logic here.

MERGED: config and base64 image encoding from Aditi; routing, generation options
and the model fallback from Sushil.
"""

import base64

import ollama

from .config import OLLAMA_BASE_URL, MODELS

# Words that suggest the user wants a calculation or code rather than prose.
# Deliberately narrow. These must only fire on a genuine calculation or code
# request - words like "report" or "analysis" belong to the general model.
CODE_HINTS = ("calculate", "compute the", "work out", "how many days",
              "average of", "sum of", "write a script", "write code",
              "python", "regex", "sql")

# num_ctx is set explicitly. Ollama defaults to 4096, and prompt + generation
# must both fit inside it: the transcript after retrieval runs ~1900 tokens,
# and num_predict reserves 1600 more, which leaves almost no headroom before
# the template turn pushes it over. An overflowing context silently returns
# empty content rather than an error.
# A reasoning model spends tokens thinking BEFORE it emits any content, and
# that thinking is drawn from the same num_predict budget. The template turn -
# regenerate a whole document shaped to a house format - makes it think longest,
# and a budget that fits the earlier turns runs out there, returning empty
# content. Budget for deliberation plus the reply, not just the reply.
OPTIONS = {"temperature": 0.2, "num_predict": 6000, "num_ctx": 16384}

# Do NOT pass think= to Ollama.
#
# With think omitted, Ollama returns everything in message.content - the
# <think> block followed by the reply - and loop._strip_reasoning removes the
# block before parsing. That works.
#
# Passing think=False switches Ollama to split output: reasoning goes to
# message.thinking and content comes back EMPTY, which the loop reads as "no
# answer". qwen3 keeps reasoning either way, so the parameter buys nothing and
# costs the reply. Left here as a named constant so nobody re-adds it.
SEND_THINK = False


_NO_THINK = set()          # models that rejected think=, remembered per run


def _chat(model: str, messages: list):
    """Call Ollama with thinking off where the model supports it.

    Non-reasoning models (coder, vision) may reject the think parameter, and
    older clients do not accept it at all. Either way, retry without it once
    and remember, so the cost is paid a single time per model.
    """
    if SEND_THINK and model not in _NO_THINK:
        try:
            return _client.chat(model=model, messages=messages,
                                options=OPTIONS, think=False)
        except TypeError:
            _NO_THINK.add(model)
        except Exception as e:
            if "think" not in str(e).lower():
                raise          # a real failure - let the caller handle it
            _NO_THINK.add(model)
    return _client.chat(model=model, messages=messages, options=OPTIONS)


def _content(res) -> str:
    """Return the model's reply.

    Ollama puts reasoning in message.thinking and the actual reply in
    message.content. Reasoning is NOT a reply - handing it back would give the
    loop prose where it needs json. If content is empty the model produced no
    answer, and the loop must retry rather than accept the deliberation.

    As a last resort we look for a json object inside the reasoning, because a
    model cut off mid-think has often already stated the call it intended.
    """
    msg = res["message"]
    text = (msg.get("content") or "").strip()
    if text:
        return text

    return _last_json_object(msg.get("thinking") or "")


def _last_json_object(text: str) -> str:
    """Return the last balanced {...} carrying a tool or answer key, or "".

    Balanced scan, not a regex - tool calls nest an args object inside, and a
    non-recursive pattern matches the inner one instead. Last, not first,
    because a model talking through its options leaves rejected calls behind.
    """
    import json as _json
    found, depth, start = [], 0, None
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
                found.append(text[start:i + 1])
                start = None
    for raw in reversed(found):
        try:
            obj = _json.loads(raw)
            if isinstance(obj, dict) and ("tool" in obj or "answer" in obj):
                return raw
        except Exception:
            pass
    return ""

_client = ollama.Client(host=OLLAMA_BASE_URL)


def encode_images(images: list) -> list:
    """Read each image from disk and base64-encode it.  Author: Aditi.

    Explicit, rather than handing Ollama a path and trusting it to read it.
    """
    out = []
    for path in images:
        with open(path, "rb") as fh:
            out.append(base64.b64encode(fh.read()).decode("utf-8"))
    return out


def pick(prompt: str, images) -> tuple[str, str]:
    """Returns (model_key, reason). Deterministic - no model involved."""
    if images:
        return "vision", "image attached"
    low = prompt.lower()
    if any(w in low for w in CODE_HINTS):
        return "coding", "calculation requested"
    return "general", "text question"


def ask_model(prompt: str, images: list = None, route_on: str = None):
    """Returns (answer, model_used, model_reason). Never raises.

    route_on: the text routing should look at. The loop sends the whole
    transcript as `prompt`, and that transcript contains the system prompt,
    which mentions "calculate", "python" and "sql" in the tool instructions.
    Matching against it sent every request to the coding model. Route on the
    user's own question instead.
    """
    key, reason = pick(route_on if route_on is not None else prompt, images)
    name = MODELS[key]

    message = {"role": "user", "content": prompt}
    if images:
        message["images"] = encode_images(images)

    try:
        res = _chat(name, [message])
        return _content(res), name, reason

    except Exception as e:
        # Fall back to the general model if the routed one is not installed.
        if key != "general":
            try:
                res = _chat(MODELS["general"],
                            [{"role": "user", "content": prompt}])
                return (_content(res), MODELS["general"],
                        reason + " (fallback)")
            except Exception:
                pass
        return (f"The model could not be reached. Is Ollama running, and has "
                f"'{name}' been pulled?  ({e})", name, "error")


if __name__ == "__main__":
    for q in ["What is 2 plus 2?", "Calculate the average of 187 and 94."]:
        a, m, r = ask_model(q)
        print(f"\nQ: {q}\n   model: {m}  ({r})\n   {a[:160]}")
