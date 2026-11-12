# Design — HR FAQ & Policy Assistant

## 1. What I am trying to solve

Employees often need quick answers to straightforward HR questions, but the actual rules are spread across policy documents. Searching those documents manually takes time, and a general-purpose chatbot can sound convincing even when it does not know the company's policy.

I approached this as a small retrieval-augmented generation system. The application should find relevant passages in the uploaded policies first. The language model should then use those passages to form an answer. If the documents do not contain enough information, the correct behaviour is to say so and point the employee to HR.

The source of truth is the uploaded policy collection. The model is not supposed to fill gaps with general HR knowledge.

## 2. Architecture and data flow

The prototype has a Streamlit frontend and a FastAPI backend. I kept the responsibilities separate: Streamlit handles interaction, while FastAPI handles ingestion, retrieval and answering.

Admin / Employee
       |
       v
Streamlit (app.py)
       |
       v
FastAPI (main.py)
       |
       v
 PDF → Markdown (if PDF)
       |
       v
 Chunking & Embeddings (chunker.py)
       |
       v
 Similarity Search (search.py)
       |
       v
  Groq LLM (rag.py)
       |
       v
Answer + Citations

### Upload flow

1. An admin selects a `.md`, `.txt`, or `.pdf` file in the Streamlit interface.
2. The frontend sends the file to the FastAPI `/upload` endpoint.
3. FastAPI checks the `x-role` header. The prototype accepts uploads only when the role is `admin`.
4. For `.pdf`, the backend temporarily writes the uploaded bytes to a PDF file and calls `pymupdf4llm.to_markdown()`. The temporary PDF is removed after conversion, and the extracted content is saved as a Markdown file in `policies/`.
5. `.md` and `.txt` files are decoded as UTF-8 text and saved in the policy directory. Text files are treated as text content; if the implementation normalizes their output name to `.md`, the content itself is not automatically given new headings.
6. `search.initialize()` reloads the policy directory, chunks the documents and rebuilds the in-memory search index.

### Question flow

1. The employee submits a question through Streamlit.
2. Streamlit sends it to FastAPI's `/ask` endpoint.
3. `rag.py` asks `search.py` for the most relevant chunks.
4. `search.py` embeds the question and compares it with the stored chunk vectors using similarity search.
5. `rag.py` checks whether the retrieved evidence is strong enough. If it is, the retrieved text is sent to the Groq chat model with instructions to answer from that context.
6. The API returns a structured result: `found`, `answer`, and `citations`.
7. If the evidence is not strong enough, the application returns a safe fallback instead of trying to answer from general knowledge.

## 3. Chunking and retrieval

### Chunking

I use a custom, section-aware Markdown chunker instead of treating the entire document as one block. It uses headings to preserve section context and handles tables separately, ensuring accurate retrieval of both paragraphs and specific table values. Each chunk also stores metadata for search and citations.

The metadata used by the search pipeline includes:

- `doc_name`: the source policy document.
- `section`: the heading or section associated with the chunk.
- `type`: the kind of chunk, such as ordinary text or table content.

The embedding input includes the document name and section along with the chunk text. This gives the embedding model some context about where the passage came from, rather than embedding an isolated sentence only.

### Embeddings and ranking

I initially used `BAAI/bge-small-en-v1.5` for faster performance. I later switched to `BAAI/bge-large-en-v1.5` to improve retrieval accuracy. The model runs locally using Sentence Transformers, with normalized embeddings and NumPy dot product for similarity search.

The current retrieval configuration uses:

- `TOP_K = 5`: retrieve up to five candidate chunks.
- `MIN_SCORE = 0.30`: use a minimum similarity threshold before treating retrieval as sufficiently relevant.

The threshold is a practical starting point, not a universal measure of correctness. Similarity scores depend on the embedding model and the documents, so this value should be checked against a small evaluation set of real policy questions.

I chose local embeddings because they avoid a paid embedding API for every upload and query. The trade-off is that the model has to be downloaded and loaded on the machine running the backend, which uses local memory and can make the first startup slower.

## 4. Grounding and refusal behaviour

The main risk in an HR assistant is a confident answer that is not actually supported by the policy. A plausible but incorrect answer about leave, benefits or reimbursements can mislead an employee.

I use multiple checks to reduce that risk:

1. **Retrieve before generating.** The language model receives policy chunks selected by the retrieval step, rather than being asked to answer an HR question without evidence.
2. **Similarity threshold.** `rag.py` uses a minimum retrieval score (`MIN_SCORE`) and a limited number of chunks (`TOP_K`). If retrieval is too weak, the application can refuse instead of generating an unsupported answer.
3. **Grounded generation.** The generation step is intended to answer using the retrieved policy context, not general model knowledge.
4. **Citations.** The response includes the document name, section and a short snippet, so the user can see which uploaded content supports the answer.
5. **Structured output.** The API returns `found`, `answer` and `citations`, rather than an unstructured paragraph alone.

The refusal path is important. For example, if an employee asks whether a personal home gym can be expensed and no uploaded policy discusses it, the assistant should say that the available policies do not provide enough information and recommend contacting HR. It should not infer an answer from common company practices.

A similarity threshold cannot prove that an answer is correct. It is one guardrail, and the quality of chunking, retrieved evidence, prompt instructions and testing all matter. I would validate the refusal threshold with examples of both answerable and unanswerable questions.

## 5. API schema

### `POST /upload`

Accepts a multipart file upload. The admin role is passed in the `x-role` header.

Supported formats in the current backend: `.md`, `.txt` and `.pdf`.

A successful response contains the uploaded filename and the current total chunk count:

```json
{
  "uploaded": "leave_policy.md",
  "total_chunks": 24
}
```

The API rejects unsupported formats, empty files and text files that cannot be decoded as UTF-8. PDF extraction errors are returned as an HTTP error rather than being silently indexed.

### `POST /ask`

Request:

```json
{
  "question": "How many casual leave days can be carried forward?"
}
```

Response:

```json
{
  "found": true,
  "answer": "The answer supported by the retrieved policy.",
  "citations": [
    {
      "doc_name": "leave_policy.md",
      "section": "Casual Leave",
      "snippet": "A short excerpt from the source chunk..."
    }
  ]
}
```

When the policy collection does not contain enough evidence, `found` should be `false`, the answer should contain the safe fallback, and citations should not imply support that was not found.

### `GET /documents`

Returns the document names represented in the current indexed chunks. This is useful for showing which policy documents are available to the assistant.

I chose a small response schema because the frontend only needs to know whether an answer was found, what the answer is, and where it came from. Keeping citations as a list also leaves room for an answer supported by more than one policy section.

## 6. Trade-offs I considered

### Local embeddings instead of a hosted embedding API

I chose `BAAI/bge-large-en-v1.5` locally rather than sending every policy passage to a hosted embedding service. This avoids a separate embedding API dependency and keeps policy text out of an additional external service for embedding. The cost is a larger model download and local compute requirements.

### NumPy similarity search instead of a vector database

I used in-memory vectors with NumPy for simplicity, as the policy collection is small. A vector database like Chroma or pgvector would offer better scalability and persistence but add complexity.

### Custom chunking instead of one generic splitter

I used a custom Markdown chunker to preserve headings, tables, and their context, improving retrieval accuracy compared to a generic text splitter.

### A simple role header instead of full authentication

The upload route checks an `x-role` header for `admin`. This is enough to demonstrate the admin-versus-employee flow in a take-home prototype, but it is not secure authentication. A real deployment would need authenticated users and server-side role assignment; clients must not be allowed to grant themselves admin access simply by setting a header.

## 7. What I would improve with two more weeks

I would focus on reliability before adding more UI features.

1. **Storing the embeddings in vectore store** Store embeddings and metadata in a persistent vector store. 
2. **A small evaluation set.** Create representative direct-fact, table-based and out-of-policy questions. Record expected answers and citations, then run them after changes to chunking, prompts or retrieval thresholds.
3. **Better PDF handling.** Test extraction against real policy PDFs, especially multi-page tables and scanned documents. Add OCR for image-only PDFs and inspect table extraction quality.
4. **Stronger authentication and upload validation.** Replace the role header with authenticated identities and server-side permissions. Add file size limits, content validation and safer handling of duplicate filenames.
5. **Feedback and monitoring.** Let employees mark an answer as helpful or not helpful. Keep enough diagnostic information to review retrieval failures without exposing sensitive policy content unnecessarily.


