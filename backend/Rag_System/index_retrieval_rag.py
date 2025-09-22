import os
import re
import json
import time
import shutil
import logging
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
load_dotenv()

import chromadb
from chromadb.config import Settings
import torch
from sentence_transformers import SentenceTransformer

from pymongo import MongoClient

# Optional: Ollama http client
import requests

LOGGER = logging.getLogger(__name__)

# --- Configuration ---
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "MockPropDB")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3-mini")
TOP_K = int(os.getenv("TOP_K", "3"))


# --- Init clients ---
device = "cuda" if torch.cuda.is_available() else "cpu"
LOGGER.info(f"[INFO] Using device for embeddings: {device}")
embedder = SentenceTransformer("sentence-transformers/all-mpnet-base-v2", device=device)

# Warmup
with torch.inference_mode():
    _ = embedder.encode(["warmup"])  # small warmup

# ensure chroma directory exists
os.makedirs(CHROMA_DIR, exist_ok=True)
client = chromadb.PersistentClient(path=CHROMA_DIR)

# Mongo
if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable is required for indexing")
mc = MongoClient(MONGO_URI)
db = mc[MONGO_DB]


def embed_text(text: str) -> List[float]:
    return embedder.encode(text).tolist()


def chunk_text_atomic(text: str, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    """Simple sentence-based chunking into atomic facts."""
    chunks = []
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    for i, s in enumerate(sentences):
        s = s.strip()
        if not s:
            continue
        chunk_id = f"file-{prefix or 'doc'}-{i+1}"
        chunks.append({"chunk_id": chunk_id, "text": s, "metadata": {"source": prefix or "file"}})
    return chunks


def chunk_doc_atomic(collection_name: str, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert a MongoDB document to small textual chunks.
    This mirrors index2.py logic but simplified and robust to missing fields.
    """
    chunks = []

    def add_chunk(text, meta_extra=None):
        base_id = doc.get("unit_id") or doc.get("amenity_id") or doc.get("tenant_id") or str(doc.get("_id"))
        idx = len(chunks) + 1
        chunk_id = f"{collection_name}-{base_id}-{idx}"
        metadata = {"collection": collection_name, "raw_json": json.dumps(doc, default=str)}
        if meta_extra:
            metadata.update(meta_extra)
        chunks.append({"chunk_id": chunk_id, "text": text, "metadata": metadata})

    try:
        # Generic flatten: iterate keys and add simple lines
        # But provide some friendly formatting for common collections
        if collection_name == "amenities":
            add_chunk(f"Amenity name: {doc.get('name')}", {"field": "name"})
            desc = doc.get('description', '')
            for i, s in enumerate(re.split(r'(?<=[.!?])\s+', desc)):
                if s.strip():
                    add_chunk(f"Amenity description sentence: {s.strip()}", {"field": f"description_{i+1}"})
            add_chunk(f"Amenity availability: {doc.get('availability')}", {"field": "availability"})
            for unit in doc.get('assigned_units', []) or []:
                add_chunk(f"Assigned unit: {unit}", {"field": "assigned_unit"})

        elif collection_name in ["contracts"]:
            add_chunk(f"Contract ID: {doc.get('contract_id')}", {"field": "contract_id"})
            add_chunk(f"Tenant: {doc.get('tenant_id')}", {"field": "tenant_id"})
            add_chunk(f"Unit: {doc.get('unit_id')}", {"field": "unit_id"})
            add_chunk(f"Monthly rent: {doc.get('monthly_rent')}", {"field": "monthly_rent"})
            add_chunk(f"Deposit: {doc.get('deposit')}", {"field": "deposit"})
            add_chunk(f"Status: {doc.get('status')}", {"field": "status"})

        elif collection_name in ["elecbill", "waterbill", "rent"]:
            add_chunk(f"Bill ID: {doc.get('bill_id')}", {"field": "bill_id"})
            add_chunk(f"Unit: {doc.get('unit_id')}", {"field": "unit_id"})
            add_chunk(f"Amount: {doc.get('amount')}", {"field": "amount"})

        else:
            # Generic: flatten each top-level primitive field into a chunk
            for k, v in doc.items():
                if isinstance(v, (str, int, float, bool)):
                    add_chunk(f"{k}: {v}", {"field": k})
                elif isinstance(v, list):
                    for item in v:
                        add_chunk(f"{k} item: {item}", {"field": k})
                else:
                    # skip complex nested for brevity
                    continue

    except Exception as e:
        LOGGER.exception("Error chunking doc: %s", e)

    return chunks


def index_collection(collection_name: str):
    coll = db[collection_name]
    LOGGER.info(f"[SYNC] Embedding documents in '{collection_name}'...")
    collection_client = client.get_or_create_collection(name=collection_name)
    for doc in coll.find():
        chunks = chunk_doc_atomic(collection_name, doc)
        for chunk in chunks:
            emb = embed_text(chunk["text"])
            collection_client.upsert(ids=[chunk["chunk_id"]], documents=[chunk["text"]], metadatas=[chunk["metadata"]], embeddings=[emb])
            LOGGER.debug(f"[UPSERT] {chunk['chunk_id']} in {collection_name}")
    LOGGER.info(f"[SYNC] Finished embedding '{collection_name}'.")


def index_files(file_paths: List[str], namespace: str = "files"):
    # use single collection for files
    collection_client = client.get_or_create_collection(name=namespace)
    for path in file_paths:
        if not os.path.exists(path):
            LOGGER.warning("File not found: %s", path)
            continue
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # chunk
        chunks = chunk_text_atomic(text, prefix=os.path.basename(path))
        for chunk in chunks:
            emb = embed_text(chunk["text"])
            mid = f"file-{os.path.basename(path)}-{chunk['chunk_id']}"
            collection_client.upsert(ids=[mid], documents=[chunk["text"]], metadatas=[chunk["metadata"]], embeddings=[emb])
            LOGGER.debug(f"[UPSERT] {mid} for file {path}")


def query_chroma(collections: Optional[List[str]], query: str, top_k: int = TOP_K):
    # compute embedding
    q_emb = embed_text(query)
    hits = []
    target_cols = collections or [c['name'] for c in client.list_collections()]
    # If collections is a list of names, use get_collection
    for col in target_cols:
        try:
            coll = client.get_collection(name=col)
        except Exception:
            # skip missing
            continue
        res = coll.query(query_embeddings=[q_emb], n_results=top_k, include=['metadatas', 'documents', 'distances'])
        ids = res.get('ids') or []
        docs = res.get('documents') or []
        metas = res.get('metadatas') or []
        dists = res.get('distances') or []
        for i in range(len(ids)):
            hits.append({
                'collection': col,
                'id': ids[i],
                'document': docs[i],
                'metadata': metas[i],
                'distance': dists[i]
            })
    # sort by distance ascending
    hits = sorted(hits, key=lambda x: x.get('distance', 0))
    return hits[:top_k]


def generate_answer_with_ollama(prompt: str) -> str:
    url = f"{OLLAMA_URL}/api/generate"
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "max_tokens": 512}
    try:
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        # Ollama response structure may vary; handle common cases
        if isinstance(data, dict) and 'text' in data:
            return data['text']
        # if streaming or content in choices
        if isinstance(data, dict) and 'choices' in data and len(data['choices']) > 0:
            return data['choices'][0].get('text', '')
        return str(data)
    except Exception as e:
        LOGGER.exception("Ollama generation failed: %s", e)
        return ""


def generate_answer(user_query: str, collections: Optional[List[str]] = None, top_k: int = TOP_K):
    hits = query_chroma(collections, user_query, top_k=top_k)
    context = []
    for h in hits:
        context.append(f"Source({h['collection']}): {h['document']}")
    context_str = "\n\n".join(context)
    prompt = f"You are a Property RAG Assistant. Answer only from context.\n[QUESTION]\n{user_query}\n[CONTEXT]\n{context_str}\n[FINAL ANSWER]"
    resp = generate_answer_with_ollama(prompt)
    if not resp:
        return "I don’t know based on available data."
    return resp


if __name__ == "__main__":
    # simple CLI for indexing and querying
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--index-all', action='store_true', help='Index all mongo collections and Company_Rules.md')
    p.add_argument('--query', type=str, help='Run a quick query')
    args = p.parse_args()
    if args.index_all:
        # index mongo
        for c in db.list_collection_names():
            index_collection(c)
        # index company rules file if exists
        rules_path = os.path.join(os.path.dirname(__file__), 'Company_Rules.md')
        if os.path.exists(rules_path):
            index_files([rules_path], namespace='files')
        LOGGER.info('Indexing complete')
    if args.query:
        print(generate_answer(args.query))
