"""
INGESTION - run by hand:  python ingest.py corpus/

Reads every PDF in a folder, cuts it into chunks, labels each chunk with a
sensitivity level, and stores them in Chroma so they can be searched.

Run this once after adding or changing documents.
"""

import sys
import pathlib

from pypdf import PdfReader
import chromadb

# ------------------------------------------------------------------ SETTINGS

CHUNK_SIZE = 800          # characters per chunk
CHUNK_OVERLAP = 100       # so a sentence split across a boundary is not lost
STORE_PATH = "./chroma"
COLLECTION = "plant_docs"

from policy import level_of as sensitivity_for   # classification from policy.yaml


def chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    out, i = [], 0
    while i < len(text):
        piece = text[i:i + size].strip()
        if piece:
            out.append(piece)
        i += size - overlap
    return out


# ------------------------------------------------------------------ INGEST

def ingest_folder(path: str, reset: bool = True) -> int:
    client = chromadb.PersistentClient(path=STORE_PATH)

    if reset:
        try:
            client.delete_collection(COLLECTION)
            print("  cleared the old index")
        except Exception:
            pass

    col = client.get_or_create_collection(COLLECTION)

    folder = pathlib.Path(path)
    pdfs = sorted(folder.glob("*.pdf"))
    # Spreadsheets are NOT chunked into the vector store - they go into SQLite
    # and are queried exactly. See structured.py.
    if not pdfs:
        print(f"  no PDFs found in {folder.resolve()}")
        return 0

    total = 0
    for pdf in pdfs:
        level = sensitivity_for(pdf.name)
        n = 0
        try:
            import registry
            reader = PdfReader(str(pdf))
        except Exception as e:
            print(f"  FAILED {pdf.name}: {e}")
            continue

        ids, docs, metas = [], [], []
        for pageno, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for j, chunk in enumerate(chunk_text(text)):
                ids.append(f"{pdf.stem}-p{pageno}-c{j}")
                docs.append(chunk)
                metas.append({"document": pdf.name,
                              "page": pageno,
                              "sensitivity": level})
                n += 1

        if n == 0:
            print(f"  {pdf.name:<32} 0 chunks  <- no text found. "
                  f"Is it a scan? OCR needed.")
            continue

        col.add(ids=ids, documents=docs, metadatas=metas)
        total += n
        # Record it in the registry and settle its effective date from its
        # own text. Without a date, a correction has nothing to outrank.
        entry = registry.register(pdf.name, level, text=" ".join(docs[:8]))
        mark = {"document": "", "default": "  (assumed)"}.get(
            entry["date_source"], "")
        print(f"  {pdf.name:<32} {n:>4} chunks  [{level}]"
              f"  eff {entry['effective']}{mark}")

    return total


# ------------------------------------------------------------------ CHECK

def ingest_one(pdf_path: str, level: str) -> int:
    """Index a single document at a given classification.

    Used by the upload endpoint. PDFs are chunked into the vector index;
    spreadsheets become SQL tables, the same split ingest_folder makes - a
    count should be answered by SELECT COUNT(*), not by similarity over
    chunked text.

    Returns the number of chunks for a PDF, or the number of rows for a sheet.
    """
    import pathlib
    pdf = pathlib.Path(pdf_path)

    if pdf.suffix.lower() in (".xlsx", ".xlsm"):
        from structured import load_one
        got = load_one(str(pdf), level)
        if not got["table"]:
            raise ValueError("The spreadsheet has no rows.")
        return got["rows"]

    client = chromadb.PersistentClient(path=STORE_PATH)
    col = client.get_or_create_collection(COLLECTION)

    # remove any previous version of this document
    try:
        col.delete(where={"document": pdf.name})
    except Exception:
        pass

    reader = PdfReader(str(pdf))
    ids, docs, metas = [], [], []
    for pageno, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for j, chunk in enumerate(chunk_text(text)):
            ids.append(f"{pdf.stem}-p{pageno}-c{j}")
            docs.append(chunk)
            metas.append({"document": pdf.name, "page": pageno,
                          "sensitivity": level})

    if not ids:
        return 0
    col.add(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def sanity_check():
    """Prove the clearance filter works, right after ingesting."""
    client = chromadb.PersistentClient(path=STORE_PATH)
    col = client.get_or_create_collection(COLLECTION)

    q = "interlock set point crude distillation column"
    tiers = {
        "Administrator   (restricted)": ["public", "internal", "restricted"],
        "Employee        (internal)":   ["public", "internal"],
        "Contractor      (public)":    ["public"],
    }

    print()
    print(f'  query: "{q}"')
    seen = {}
    for who, allowed in tiers.items():
        r = col.query(query_texts=[q], n_results=5,
                      where={"sensitivity": {"$in": allowed}})
        docs = {m["document"] for m in r["metadatas"][0]}
        seen[who] = docs
        print(f"  {who:<30} {len(r['documents'][0])} passages")

    top = list(tiers)[0]
    for who in list(tiers)[1:]:
        hidden = seen[top] - seen[who]
        if hidden:
            print(f"  hidden from {who.split('(')[0].strip()}: "
                  f"{', '.join(sorted(hidden))}")

    if seen[top] != seen[list(tiers)[-1]]:
        print("\n  CLEARANCE FILTER WORKING")
    else:
        print("\n  WARNING: every role sees the same documents.")
        print("  Check CLASSIFICATION matches real filenames, and that the")
        print("  restricted documents contain text relevant to this query.")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "corpus/"
    print(f"ingesting {folder}")
    total = ingest_folder(folder)
    print(f"\n  {total} chunks stored in {STORE_PATH}")

    # Spreadsheets go to SQLite, never to the vector store.
    from structured import load_workbooks
    books = load_workbooks(folder)
    if books:
        print("\n  spreadsheets loaded as tables:")
        for b in books:
            print(f'    {b["source_file"]:<32} -> {b["table"]}  '
                  f'{b["rows"]} rows  [{b["sensitivity"]}]')

    if total:
        sanity_check()
