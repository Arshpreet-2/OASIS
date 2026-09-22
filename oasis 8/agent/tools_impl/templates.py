"""Finding the organisation's own document templates in the corpus.

Called from agent/loop.py before a write tool runs, so the house format cannot
be forgotten. A document only counts as a template if its filename says so.
"""


TEMPLATE_FOR = {
    "write_docx": {
        "query": "approval note letter report template format structure",
        "tokens": ("approval", "note", "letter", "report", "memo"),
    },
    "write_pptx": {
        "query": "presentation deck briefing template format structure",
        "tokens": ("presentation", "deck", "briefing", "slide"),
    },
    "write_xlsx": {
        "query": "spreadsheet register log template format structure",
        "tokens": ("spreadsheet", "register", "log", "sheet"),
    },
}


def house_deck(user_level: str = "restricted") -> str:
    """Path to the organisation's own deck template, if the caller may use it.

    A deck template is a file, not text: python-pptx opens it and inherits the
    master, so the branding is exact. That is why this returns a path where
    available_templates returns prose.
    """
    import pathlib

    from policy import allowed_levels, level_of

    deck = pathlib.Path("corpus") / "template_deck.pptx"
    if not deck.exists():
        return ""
    level = level_of(deck.name)
    if level and level not in allowed_levels(user_level):
        return ""
    return str(deck)


def available_templates(user_level: str = "restricted") -> list:
    """Every house template the caller may see, as {document, text}.

    Listed for the model rather than selected for it. Which template - or
    whether a template applies at all - depends on what the user asked, and
    the user's sentence is already in the prompt. Code guessing from keywords
    is a second, worse reader of the same words.
    """
    from my_rag import library, search

    out, seen = [], set()
    for doc in library():
        name = doc["document"]
        if "template" not in name.lower():
            continue
        if name in seen:
            continue
        seen.add(name)
        try:
            passages, _ = search(name.replace("_", " ").replace(".pdf", ""),
                                 user_level, k=4)
        except Exception:
            continue
        text = "\n".join(p["text"] for p in passages
                          if p["document"] == name)
        if text.strip():
            out.append({"document": name, "text": text})
    return out


def find_template(tool_name: str, user_level: str = "restricted",
                  hint: str = ""):
    """Look in the corpus for the organisation's own template for this kind of
    document. Returns its text, or None if the plant has not supplied one.

    Called in code rather than left to the model, so it cannot be forgotten.
    A document only counts as a template if its filename says so.
    """
    from my_rag import search

    spec = TEMPLATE_FOR.get(tool_name)
    if not spec:
        return None

    query = f"{hint} {spec['query']}".strip()
    try:
        passages, _ = search(query, user_level, k=6)
    except Exception:
        return None

    # Score each candidate template: does the request itself name it?
    # "draft an email" should reach the letter template, not the approval note.
    NAMES = {
        "approval": ("approval", "sanction", "authorise", "authorize"),
        "note": ("note", "memo"),
        "letter": ("letter", "email", "mail", "correspondence", "write to"),
        "report": ("report", "analysis", "study", "findings"),
        "register": ("register", "log", "list", "table"),
        "presentation": ("presentation", "deck", "slide", "ppt", "briefing"),
    }
    low = (hint or "").lower()

    scores = {}
    for p in passages:
        name = p["document"].lower()
        if "template" not in name:
            continue
        if not any(tok in name for tok in spec["tokens"]):
            continue
        score = scores.get(p["document"], 0)
        for key, words in NAMES.items():
            if key in name and any(w in low for w in words):
                score += 10
        score += 1                       # retrieval already ranked it
        scores[p["document"]] = score

    if not scores:
        return None
    best = max(scores, key=scores.get)

    text = "\n".join(p["text"] for p in passages if p["document"] == best)
    return {"document": best, "text": text[:2500]}
