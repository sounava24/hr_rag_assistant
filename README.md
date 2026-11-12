# HR Policy Assistant

A small HR FAQ assistant built around retrieval-augmented generation (RAG). The idea is simple: instead of asking a chatbot to answer HR questions from its general knowledge, the application first searches the HR policy documents that have been uploaded and then uses the relevant passages to prepare an answer.

I built this as a practical prototype for the HR FAQ & Policy Assistant take-home assignment. I wanted the system to be useful for everyday policy questions, but also careful about the cases where the documents do not contain an answer.

## What it does

- Lets an admin upload HR policy documents in `.md`, `.txt`, or `.pdf` format.
- Converts uploaded PDFs into Markdown before indexing them.
- Splits Markdown policy content into smaller, searchable chunks. The chunking logic also handles section headings and tables.
- Creates local text embeddings and searches for chunks that are relevant to an employee's question.
- Uses the retrieved policy content to generate an answer.
- Returns a structured response containing the answer, whether relevant information was found, and citations.
- Uses a fallback response when the retrieved policy content is not strong enough to support an answer.

The assistant is intended to answer from the uploaded policies, not from general HR knowledge. If a policy does not cover a question, it should say that it does not have enough information and direct the employee to HR.

## Tech stack

| Part | Technology |
|---|---|
| Frontend | Streamlit |
| Backend API | FastAPI |
| Request / response validation | Pydantic |
| Embeddings | `BAAI/bge-large-en-v1.5` through Sentence Transformers |
| Similarity search | NumPy dot product over normalized vectors |
| LLM answer generation | Groq API |
| PDF extraction | `pymupdf4llm` |
| Policy formats | Markdown, text, PDF |

The embedding model runs locally through Sentence Transformers. The final answer is generated through Groq's hosted API. The default chat model is `llama-3.3-70b-versatile`, and it can be overridden with the `LLM_MODEL` environment variable.

## How the application is organised

The main files are:

```text
hr_rag/
├── app.py                 # Streamlit user interface
├── main.py                # FastAPI application and API endpoints
├── rag.py                 # Retrieval + LLM answer generation
├── search.py               # Document loading, embeddings and similarity search
├── chunker.py              # Markdown and table-aware chunking
├── policies/               # Uploaded / indexed HR policy documents (PLEASE UPLOAD THE FILES)
├── requirements.txt
├── .env                    # Local secrets; do not commit
├── .env.example            # Example environment variables
├── .gitignore
├── README.md
└── DESIGN.md
```

This is the logical structure of the project. If your local filenames differ, update this section to match the repository before publishing it.

## Run locally

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd hr_rag_assistant
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can use Command Prompt instead:

```bat
venv\Scripts\activate
```

### 3. Install dependencies

If requirements.txt is included:

```pip install -r requirements.txt```

The main packages used by the application include:

```pip install fastapi uvicorn python-multipart pydantic streamlit requests numpy sentence-transformers pymupdf4llm```


### 4. Configure the Groq API key

Create a `.env` file locally, or set the environment variable in your terminal. Do not commit the real key.

PowerShell example:

```powershell
$env:GROQ_API_KEY="your_groq_api_key"
$env:LLM_MODEL="llama-3.3-70b-versatile"
```

The embedding model `BAAI/bge-small-en-v1.5` is loaded locally by Sentence Transformers. On its first run, the model files may need to be downloaded, so the first startup can take longer and requires an internet connection.

### 5. Add the .md files in policies folder

leave-policy.md , it-security-policy.md, benefits-policy.md and others are to be inlcuded.

### 6. Start the FastAPI backend

Open a terminal with the virtual environment activated:

```powershell
uvicorn main:app --reload
```

The API will normally be available at:

```text
http://127.0.0.1:8000
```

FastAPI's interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

### 7. Start the Streamlit frontend

Open a second terminal, activate the same virtual environment, and run:

```powershell
streamlit run app.py
```

Streamlit will print the local URL in the terminal (usually `http://localhost:8501`).

## Using the application

1. Start the backend and frontend.
2. Open the Streamlit page.
3. Use the admin upload option to add an HR policy document.
4. The backend checks the file type. Markdown and text files are read as text; PDFs are converted to Markdown using `pymupdf4llm`.
5. The converted or original text is saved under `policies/`, and the search index is initialized again.
6. Ask a question in natural language.
7. Review the answer and its citations. If the policies do not provide enough evidence, the assistant should return its safe fallback rather than inventing an answer.

### API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/upload` | Upload a policy document. Admin role is checked through the `x-role` header. |
| `POST` | `/ask` | Submit a question and receive a structured answer with citations. |
| `GET` | `/documents` | List document names represented in the current search chunks. |

Example question request:

```json
{
  "question": "How many casual leave days can be carried forward?"
}
```

The response schema is:

```json
{
  "found": true,
  "answer": "Answer supported by the retrieved policy content.",
  "citations": [
    {
      "doc_name": "leave_policy.md",
      "section": "Casual Leave",
      "snippet": "A short excerpt from the supporting chunk..."
    }
  ]
}
```

The exact answer and citations depend on the documents that have been uploaded.

## A few implementation notes

- The search index is currently built in memory. It is initialized when FastAPI starts and rebuilt after a successful upload. This keeps the prototype straightforward, but it means the embeddings are not stored in a persistent vector database.
- PDF conversion is text extraction, not a guarantee of perfect OCR. Scanned PDFs or complicated layouts may need OCR or manual checking. Tables should always be checked after extraction.
- The upload role check is a simple `x-role` header for this prototype. It is not production authentication.
- Uploaded policy documents may contain confidential information. Only use documents that you are permitted to upload, and do not commit private company policies to a public repository.
- Do not commit `.env`, API keys, virtual environments, caches, or local secrets.

## Current limitations and next steps

This is a prototype, not a production HR system. The first things I would improve are persistent indexing and document version handling, stronger authentication, a small set of test questions with expected citations, and more robust handling of scanned PDFs and complex policy tables. I would also add feedback on answers so incorrect or unhelpful responses can be reviewed.

## Assignment fit

The project focuses on the core requirements: policy document ingestion, semantic retrieval, grounded answers, citations, and a safe fallback when the uploaded policies do not support an answer. The design decisions and current limitations are explained in [DESIGN.md](DESIGN.md).
