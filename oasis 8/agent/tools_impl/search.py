"""Tool: search the document library. READ-ONLY.

The clearance filter lives in my_rag.search, so every retrieval the agent makes
goes through it. There is no other route to the documents.
"""


def tool_search(question: str, user_level: str, k: int = 5, **_ignored):
    """Search the document library at the caller's clearance."""
    from my_rag import search
    passages, excluded = search(question, user_level, k)
    if not passages:
        return {"found": 0, "excluded": excluded, "passages": []}
    return {"found": len(passages), "excluded": excluded,
            "passages": [{"text": p["text"][:1200],
                          "document": p["document"],
                          "page": p["page"]} for p in passages]}
