# Building the RAG layer

Your part. Everything the workbench actually demonstrates runs through here.

Two files: `ingest.py` puts documents in, `my_rag.py` gets the right bits out.

---

## 1. What RAG is, in six steps

The model knows nothing about this refinery. It has never seen your manuals, and
you cannot paste a 400-page PDF into every question. So before answering, you go
and find the few paragraphs that are actually relevant and paste only those in.

    1. CUT       documents into chunks of a few paragraphs
    2. REMEMBER  which document and which page each chunk came from
    3. EMBED     turn each chunk into a list of numbers capturing its meaning
    4. STORE     put those numbers in a vector database (Chroma)
    5. SEARCH    turn the question into numbers, find the closest chunks
    6. ANSWER    paste those chunks into the prompt with the question

Steps 1–4 are `ingest.py`, run once by hand. Steps 5–6 are `my_rag.py` plus the
prompt building already in `server.py`.

**Three of our features are just changes to these steps, not separate systems:**

| Feature | Where it lives |
|---|---|
| Clearance filtering | step 5 — a filter on the query |
| Page citations | step 2 — because you saved the page number |
| Refusing to guess | step 6 — the prompt instruction, plus an empty-result check |

---

## 2. Install

    source sih-venv/bin/activate
    pip install chromadb pypdf

Chroma includes its own embedding model, so nothing else is needed to start.

---

## 3. Ingestion — `ingest.py`

### Reading a PDF page by page

    from pypdf import PdfReader

    reader = PdfReader("corpus/pump_manual_p101.pdf")
    for pageno, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

Page by page, not the whole file at once. That is how you get page numbers, and
page numbers are what make citations possible.

`extract_text()` returns nothing for a scanned PDF, because a scan is a picture.
That is what OCR solves — leave it for later and use text PDFs today.

### Chunking

    CHUNK = 800
    OVERLAP = 100

    def chunk_text(text):
        out, i = [], 0
        while i < len(text):
            out.append(text[i:i + CHUNK])
            i += CHUNK - OVERLAP
        return out

Overlap matters: without it, a sentence split across a boundary is lost from
both chunks. 800 characters is a sensible start — tune it later against your
test questions.

### Labelling sensitivity

    RESTRICTED = ["hazop_report.pdf"]

    def sensitivity_for(name):
        return "restricted" if name in RESTRICTED else "normal"

**The label goes on every chunk, not just the document.** Search works on chunks,
so that is where the label has to live. Getting this wrong makes the whole
clearance feature silently useless — it will look like it works.

### Storing

    import chromadb

    client = chromadb.PersistentClient(path="./chroma")
    col = client.get_or_create_collection("plant_docs")

    col.add(
        ids=[f"{pdf.name}-{pageno}-{j}"],
        documents=[chunk],
        metadatas=[{"document": pdf.name,
                    "page": pageno,
                    "sensitivity": sensitivity_for(pdf.name)}],
    )

`PersistentClient` writes to disk, so the index survives a restart. Chroma
embeds the text for you.

Ids must be unique — filename plus page plus chunk number guarantees that.

### Run it

    python ingest.py corpus/

It should print how many chunks were stored. If it says zero, the PDFs are
scans and `extract_text()` found nothing.

---

## 4. Retrieval — `my_rag.py`

### The contract

    search(question: str, user_level: str, k: int = 5) -> (passages, excluded_count)

    passage = {"text", "document", "page", "sensitivity"}

`server.py` calls exactly this. Do not change the shape.

### The search

    def search(question, user_level="normal", k=5):
        allowed = ["normal"] if user_level == "normal" else ["normal", "restricted"]

        res = col.query(
            query_texts=[question],
            n_results=k,
            where={"sensitivity": {"$in": allowed}},
        )

        passages = [
            {"text": doc,
             "document": meta["document"],
             "page": meta["page"],
             "sensitivity": meta["sensitivity"]}
            for doc, meta in zip(res["documents"][0], res["metadatas"][0])
        ]

        unfiltered = col.query(query_texts=[question], n_results=k)
        excluded = len(unfiltered["documents"][0]) - len(passages)

        return passages, max(0, excluded)

### The one line that matters

    where={"sensitivity": {"$in": allowed}}

That is the entire differentiator. It tells Chroma not to look at restricted
chunks at all.

**Wrong — looks identical, is not secure:**

    res = col.query(query_texts=[question], n_results=k)
    passages = [p for p in results if p["sensitivity"] in allowed]

The restricted chunk was fetched, sat in memory, and passed through the system.
A cleverly worded question could still surface it. **Never retrieved means never
leaked** — that is the claim, and it has to be true.

### The excluded count

The second unfiltered query exists only so the interface can show "1 excluded by
clearance". It is not a security control — it just tells the user something was
withheld, which is what makes the demo visible.

---

## 5. Testing it — do this before anything else

    from my_rag import search

    a, ea = search("interlock set point", "restricted")
    b, eb = search("interlock set point", "normal")

    print(len(a), "passages for admin, excluded", ea)
    print(len(b), "passages for contractor, excluded", eb)

Admin should get more passages than the contractor, and the contractor's
excluded count should be above zero.

**When those two lines print different numbers, your differentiator works.**
Everything after that is assembly.

---

## 6. How it connects

`server.py` imports it directly:

    from my_rag import search, library

`search` is called by the agent's `search_documents` tool, so every retrieval
the agent performs goes through the clearance filter. There is no other route to
the documents.

## 7. Tuning, if there is time

**Chunk size.** Too small and each chunk loses its context; too large and the
search goes vague. Try 500, 800 and 1200 against your test questions and keep
whichever answers best.

**Reranking.** Fetch 20 candidates, re-score them with a small cross-encoder,
keep the best 5. This improves answers more per hour of work than anything else
here — but measure it rather than assuming.

**Number of results.** `k=5` is a reasonable default. More context is not always
better; irrelevant chunks actively make answers worse.

---

## 8. When it goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Ingestion stores 0 chunks | PDFs are scans | Use text PDFs, or add OCR |
| Every question returns the same chunks | Query text not reaching Chroma | Check `query_texts=[question]`, note the list |
| Contractor sees restricted material | Filter applied after the query, or labels on documents not chunks | Move the filter into `where=` |
| `excluded_count` always 0 | Nothing restricted in the corpus | Check `RESTRICTED` matches a real filename |
| Citations show `None` for page | Page number lost during chunking | Ingest page by page, not whole file |
| Answers ignore the documents | Prompt not instructing the model | `server.py` already handles this — check passages are non-empty |
| Chroma index seems stale | Old data still stored | Delete `./chroma` and re-ingest |

---

## 9. The order to build in

1. Read one PDF and print its text. Confirm it works.
2. Chunk it and print the first three chunks with page numbers.
3. Store in Chroma. Confirm the count.
4. Search without any filter. Confirm sensible chunks come back.
5. Add the `where` clause. Run the two-user test in section 5.
6. Swap the line in `server.py`. Test through the interface.

Do not skip to step 5. Each step is checkable in ten seconds, and a mistake in
step 2 is invisible until step 5 if you rush.
