"""
RETRIEVAL - the real search. Used by server.py.

    search(question, user_level, k) -> (passages, excluded_count)
    passage = {"text", "document", "page", "sensitivity"}

THE LINE THAT MATTERS is the `where=` clause. It tells Chroma not to look at
chunks above the user's clearance at all, so they are never fetched. Do NOT
search everything and filter the results afterwards - it looks identical in a
demo and is not secure.
"""

import chromadb

STORE_PATH = "./chroma"
COLLECTION = "plant_docs"

from policy import allowed_levels, levels as _levels

LEVELS = _levels()

_client = chromadb.PersistentClient(path=STORE_PATH)


def _col():
    return _client.get_or_create_collection(COLLECTION)


def search(question: str, user_level: str = "public", k: int = 5):
    allowed = allowed_levels(user_level)
    col = _col()

    res = col.query(
        query_texts=[question],
        n_results=k,
        where={"sensitivity": {"$in": allowed}},      # <- the clearance filter
    )

    passages = [
        {"text": doc,
         "document": meta["document"],
         "page": meta["page"],
         "sensitivity": meta["sensitivity"]}
        for doc, meta in zip(res["documents"][0], res["metadatas"][0])
    ]

    # How many of the best matches were withheld. Display only, not a control.
    everything = col.query(query_texts=[question], n_results=k)
    excluded = sum(1 for m in everything["metadatas"][0]
                   if m["sensitivity"] not in allowed)

    return passages, excluded


def library():
    """Every indexed document with its level and chunk count. For the admin tab."""
    col = _col()
    got = col.get(include=["metadatas"])
    seen = {}
    for m in got["metadatas"]:
        d = m["document"]
        if d not in seen:
            seen[d] = {"document": d, "sensitivity": m["sensitivity"], "chunks": 0}
        seen[d]["chunks"] += 1
    return sorted(seen.values(), key=lambda x: x["document"])


if __name__ == "__main__":
    q = "interlock set point crude distillation column"
    for lvl in LEVELS[::-1]:
        p, e = search(q, lvl)
        docs = ", ".join(sorted({x["document"] for x in p}))
        print(f"{lvl:>11}: {len(p)} passages, {e} excluded -> {docs}")
    print("\nlibrary:")
    for d in library():
        print(f"  {d['document']:<32} {d['sensitivity']:<11} {d['chunks']} chunks")
