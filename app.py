# app.py
import os, re, json
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from gpt4all import GPT4All

load_dotenv()
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
GPT4ALL_MODEL = os.getenv("GPT4ALL_MODEL", "./models/gpt4all-model.bin")

# Init
emb_model = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=CHROMA_DIR))
# load or get a default collection (we'll assume 'bills' for this example)
collection = chroma_client.get_collection("bills")

# init local LLM
gpt = GPT4All(GPT4ALL_MODEL)

app = FastAPI()

class QueryIn(BaseModel):
    question: str
    top_k: int = 3

unit_pattern = re.compile(r"\bU[- ]?(\d+)\b", re.IGNORECASE)

@app.post("/query")
def query(q: QueryIn):
    question = q.question
    # 1) try to extract a unit_id like "U-101" or "unit 101"
    m = unit_pattern.search(question)
    where = None
    if m:
        unit_id = f"U-{m.group(1)}"
        where = {"unit_id": unit_id}
    # 2) embed & run chroma query (metadata filter if available)
    query_emb = emb_model.encode(question).tolist()
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=q.top_k,
        where=where
    )
    docs = []
    # results["documents"] is list of lists (one per query), we take first
    if results and results.get("documents"):
        docs = results["documents"][0]
        metas = results["metadatas"][0]
    else:
        docs = []
        metas = []

    # 3) Build context summary
    context_parts = []
    for d, m in zip(docs, metas):
        context_parts.append(f"- {d} (meta: {m})")
    context_text = "\n".join(context_parts) if context_parts else "No relevant records found."

    # 4) Prompt template (instruct to only use context)
    prompt = (
        "You are a property management assistant. Answer the user's question using ONLY the information in the 'Context' below.\n\n"
        "Context:\n"
        f"{context_text}\n\n"
        f"User question: {question}\n\n"
        "Answer succinctly and include the source bill_id or mongo_id if possible."
    )

    # 5) Generate with GPT4All
    resp = gpt.generate(prompt, max_tokens=200, temperature=0.0)
    if isinstance(resp, (list, tuple)):
        # GPT4All might return a generator or list; join to string
        answer = " ".join(map(str, resp))
    else:
        answer = str(resp)

    return {"answer": answer, "context_count": len(docs), "context": context_parts}
