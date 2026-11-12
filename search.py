
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from chunker import chunk_markdown

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

chunks = []
vecs = np.empty((0, 0))


def initialize(policy_dir="policies"):
    global chunks, vecs

    chunks = []
    for ext in ("*.md", "*.txt"):
        for f in Path(policy_dir).glob(ext):
            chunks += chunk_markdown(
                f.read_text(encoding="utf-8"),
                f.name
            )

    if not chunks:
        vecs = np.empty((0, 0))
        return

    texts = [
        f'{c["doc_name"]} | {c["section"]}\n{c["text"]}'
        for c in chunks
    ]

    vecs = model.encode(
        texts,
        normalize_embeddings=True
    )


def search(q, k=5):

    if not chunks:
        return []

    qv = model.encode(
        [QUERY_PREFIX + q],
        normalize_embeddings=True
    )[0]

    scores = vecs @ qv
    idx = np.argsort(-scores)[:k]

    return [
        (chunks[i], float(scores[i]))
        for i in idx
    ]


if __name__ == "__main__":

    initialize()

    questions = [
        "What is the casual leave carry-forward limit?",
        "Does the Standard health tier cover dental implants?",
        "Can I expense a personal home gym?",
        "Do I get a work-from-home internet stipend?",
        "How many days of maternity leave do I get?",
        "What is the capital of France?",
    ]

    for q in questions:
        print("\nQ:", q)

        for c, score in search(q):
            print(
                f"  {score:.3f}  "
                f"{c['doc_name']} | {c['section']} | {c['type']}"
            )
