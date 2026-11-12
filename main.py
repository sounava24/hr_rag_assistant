
from contextlib import asynccontextmanager
from pathlib import Path
import tempfile

import pymupdf4llm

from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from pydantic import BaseModel

import rag
import search


POLICY_DIR = Path("policies")
POLICY_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    search.initialize(str(POLICY_DIR))
    yield


app = FastAPI(
    title="Interview Purpose - RAG HR Assistant",
    lifespan=lifespan
)


class AskRequest(BaseModel):
    question: str


class Citation(BaseModel):
    doc_name: str
    section: str
    snippet: str


class AskResponse(BaseModel):
    found: bool
    answer: str
    citations: list[Citation]


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    return rag.ask(req.question)


@app.post("/upload")
def upload(
    file: UploadFile = File(...),
    x_role: str = Header(default="employee")
):
    if x_role != "admin":
        raise HTTPException(403, "Admin only")

    try:
        name = (file.filename or "").replace("\\", "/").split("/")[-1]

        if not name or name in (".", ".."):
            raise HTTPException(400, "Invalid filename")

        suffix = Path(name).suffix.lower()

        if suffix not in (".md", ".txt", ".pdf"):
            raise HTTPException(
                400,
                "Only .pdf, .md and .txt files are supported"
            )

        raw = file.file.read()

        if not raw:
            raise HTTPException(400, "File is empty")

        # PDF -> Markdown conversion
        if suffix == ".pdf" :

            with tempfile.NamedTemporaryFile(
                suffix=".pdf",
                delete=False
            ) as temp:

                temp.write(raw)
                temp_path = Path(temp.name)

            try:
                text = pymupdf4llm.to_markdown(str(temp_path))

            except Exception:
                raise HTTPException(
                    400,
                    "Unable to extract text from PDF"
                )

            finally:
                temp_path.unlink(missing_ok=True)

            # Save converted PDF as Markdown
            name = Path(name).stem + ".md"

        else:
            # Directly read Markdown / TXT
            try:
                text = raw.decode("utf-8")

            except UnicodeDecodeError:
                raise HTTPException(
                    400,
                    "File is not valid UTF-8 text"
                )

        if not text.strip():
            raise HTTPException(
                400,
                "Document contains no extractable text"
            )

        # Save document
        (POLICY_DIR / name).write_text(
            text,
            encoding="utf-8"
        )

        # Rebuild search index
        search.initialize(str(POLICY_DIR))

        return {
            "uploaded": name,
            "total_chunks": len(search.chunks)
        }

    finally:
        file.file.close()


@app.get("/documents")
def documents():
    return sorted({
        c["doc_name"] for c in search.chunks
    })
