
import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import json
import requests
from dotenv import load_dotenv
from pydantic import BaseModel
from search import search

load_dotenv()

MIN_SCORE = 0.30
TOP_K = 5

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

FALLBACK = (
    "I don't have enough information in the uploaded policies "
    "to answer this. Please contact HR for clarification."
)


class LLMOut(BaseModel):
    found: bool
    answer: str
    sources: list[int]


SYSTEM = """You answer employee questions using ONLY the numbered policy excerpts provided.
Rules:
- Never use outside knowledge. Never guess or infer policy that is not written.
- If the excerpts state the answer (including a statement that something is NOT covered or NOT allowed), answer it and set found=true.
- If the excerpts do not address the question, set found=false and answer="".
- If the excerpts only say a topic is not defined in this policy or is covered elsewhere, say exactly that and tell the employee to check with HR. Do NOT say the benefit does not exist.
- List in "sources" the numbers of the excerpts that support your answer.
- For tables, read the row for exactly the tier/band asked about.
Reply with JSON only: {"found": bool, "answer": str, "sources": [int]}"""


def call_llm(context, question):
    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"},
        json={
            "model": os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            "temperature": 0,
            "max_completion_tokens": 2000,
            "reasoning_effort": "low",
            "messages": [
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": f"Excerpts:\n{context}\n\nQuestion: {question}"
                },
            ],
        },
        timeout=30,
    )

    if resp.status_code != 200:
        print("HTTP", resp.status_code, resp.text)
        resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"]
    return LLMOut.model_validate(json.loads(content))


def ask(question):
    question = (question or "").strip()

    if not question:
        return {
            "found": False,
            "answer": "Please enter a question.",
            "citations": []
        }

    # Retrieve relevant chunks using search.py
    hits = search(question, k=TOP_K)

    if not hits or hits[0][1] < MIN_SCORE:
        return {
            "found": False,
            "answer": FALLBACK,
            "citations": []
        }

    context = "\n\n".join(
        f'[{n}] ({c["doc_name"]} > {c["section"]})\n{c["text"]}'
        for n, (c, _) in enumerate(hits, 1)
    )

    try:
        out = call_llm(context, question)
    except Exception as e:
        print("LLM error:", e)
        return {
            "found": False,
            "answer": FALLBACK,
            "citations": []
        }

    # Build citations from actual retrieved chunks
    valid = [
        n for n in out.sources
        if 1 <= n <= len(hits)
    ]

    if not out.found or not valid:
        return {
            "found": False,
            "answer": FALLBACK,
            "citations": []
        }

    citations = [
        {
            "doc_name": hits[n-1][0]["doc_name"],
            "section": hits[n-1][0]["section"],
            "snippet": hits[n-1][0]["text"][:200]
        }
        for n in valid
    ]

    return {
        "found": True,
        "answer": out.answer,
        "citations": citations
    }


if __name__ == "__main__":

    questions = [
        "What is the casual leave carry-forward limit?",
        "Does the Standard health tier cover dental implants?",
        "Can I expense a personal home gym?",
        "Do I get a work-from-home internet stipend?",
        "How many days of maternity leave do I get?",
        "What is the capital of France?",
        ""
    ]

    for q in questions:
        print("\nQ:", q)
        print(json.dumps(ask(q), indent=2, ensure_ascii=False))
