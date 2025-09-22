import os
import re
import json
import time
from dotenv import load_dotenv
import chromadb
import torch
from sentence_transformers import SentenceTransformer
import ollama
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Optional,  Union

load_dotenv()

DEBUG_MODE = True

# --- Config ---
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3-mini")  # Use the name you created
TOP_K = 2  # reduced for speed

# --- Init Clients ---
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INFO] Using device for embeddings: {device}")

embedder = SentenceTransformer(
    "sentence-transformers/all-mpnet-base-v2",
    device=device
)

# Warmup embedding model
with torch.inference_mode():
    _ = embedder.encode(["warmup"])  

try:
    client = chromadb.PersistentClient(path=CHROMA_DIR)
except Exception as e:
    raise RuntimeError(f"[ERROR] Failed to initialize Chroma client: {e}")

# --- Timing helper ---
def timed_step(label, func, *args, **kwargs):
    start = time.perf_counter()
    result = func(*args, **kwargs)
    end = time.perf_counter()
    print(f"[TIMER] {label}: {(end - start) * 1000:.2f} ms")
    return result

# --- Keyword mapping for collections ---
COLLECTION_KEYWORDS = {
    "Units": ["unit", "apartment", "floor", "level", "number", "room", "block", "building", "lot"],
    "Tenants": ["tenant", "name", "contact", "email", "occupant", "resident"],
    "Amenities": ["pool", "gym", "facility", "facilities", "amenity", "recreation", "assigned units"],
    "Maintenance": ["issue", "repair", "broken", "clogged", "maintenance", "status", "request", "fix"],
    "Contracts": ["contract", "lease", "rent agreement", "deposit", "start date", "end date", "monthly rent"],
    "Rent": ["rent", "payment", "paid", "unpaid", "due", "month"],
    "ElecBill": ["electricity", "elec", "bill", "power", "paid", "unpaid"],
    "WaterBill": ["water", "bill", "paid", "unpaid"],
    "Expenses": ["expense", "cost", "category", "amount", "date", "repair", "maintenance"],
    "Staff": ["staff", "employee", "worker", "assigned", "role", "contact"]
}

FAST_CACHE = {}

# --- Helper Functions ---
def generate_answer_with_ollama(prompt: str):
    try:
        start = time.perf_counter()
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        end = time.perf_counter()
        print(f"[TIMER] Ollama generation: {(end - start) * 1000:.2f} ms")

        return response.message.content if response and response.message else "[ERROR] No response from Ollama."
    except Exception as e:
        return f"[ERROR] Ollama call failed: {e}"

@lru_cache(maxsize=512)
def cached_embedding(text: str):
    with torch.inference_mode():
        return embedder.encode(text, convert_to_numpy=True).tolist()

def expand_query(user_query: str) -> list[str]:
    expansions = [user_query]
    match = re.search(r"\bU-\d{3}\b", user_query, re.IGNORECASE)
    if match:
        unit_id = match.group().upper()
        expansions.extend([f"Unit {unit_id}", f"Apartment {unit_id}", f"Property {unit_id}"])
    if "rent" in user_query.lower():
        expansions.extend(["lease", "rental fee", "monthly rent"])
    if "tenant" in user_query.lower():
        expansions.extend(["occupant", "resident", "renter"])
    return list(sorted(set(expansions)))

def detect_collections(user_query: str) -> list[str]:
    q = user_query.lower()
    selected = []
    for coll_name, keywords in COLLECTION_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(k.lower())}\b", q) for k in keywords):
            selected.append(coll_name)
    return selected or ["Units"]

def average_embeddings(embeddings: list[list[float]]) -> list[float]:
    return [sum(vals) / len(vals) for vals in zip(*embeddings)]

def retrieve_chunks(user_query: str):
    expanded_queries = expand_query(user_query)
    target_collections = detect_collections(user_query)
    unit_match = re.search(r"\bU-\d{3}\b", user_query, re.IGNORECASE)
    target_unit = unit_match.group().upper() if unit_match else None

    # --- Timing embeddings ---
    start = time.perf_counter()
    query_embeddings = [cached_embedding(q) for q in expanded_queries]
    final_query_embedding = average_embeddings(query_embeddings)
    end = time.perf_counter()
    print(f"[TIMER] Embedding + expansion: {(end - start) * 1000:.2f} ms")

    results_list = []
    all_assigned_units = []

    def query_collection(coll_name):
        try:
            collection = client.get_collection(coll_name)
            s = time.perf_counter()
            results = collection.query(
                query_embeddings=[final_query_embedding],
                n_results=TOP_K,
                where={"unit_id": {"$eq": target_unit}} if target_unit else None
            )
            e = time.perf_counter()
            print(f"[TIMER] Chroma query ({coll_name}): {(e - s) * 1000:.2f} ms")
            return coll_name, results
        except Exception as e:
            print(f"[WARN] Query failed on {coll_name}: {e}")
            return coll_name, None

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(query_collection, coll) for coll in target_collections]
        for future in as_completed(futures):
            coll_name, res = future.result()
            if res:
                if coll_name == "Amenities":
                    metadatas = res.get("metadatas")
                    if metadatas and isinstance(metadatas, list) and len(metadatas) > 0:
                        for meta in metadatas[0]:
                            raw = meta.get("raw_json")
                            if isinstance(raw, str):
                                try:
                                    amenity_doc = json.loads(raw)
                                    all_assigned_units.extend([u.upper() for u in amenity_doc.get("assigned_units", [])])
                                except json.JSONDecodeError:
                                    continue
                results_list.append(res)

    return results_list, target_collections, list(sorted(set(all_assigned_units)))

def generate_answer(user_query: str, results=None, collection_name: Optional[Union[str, list[str]]] = None, assigned_units=None, return_results=True):
    if results is None:
        results, target_collections, assigned_units = retrieve_chunks(user_query)

    start = time.perf_counter()
    chunks = []
    metadatas = []
    for r in results:
        docs = r.get("documents", [[]])[0]
        metas = r.get("metadatas", [[]])[0]
        chunks.extend(docs)
        metadatas.extend(metas)

    context = []
    for i, chunk in enumerate(chunks):
        meta = metadatas[i] if i < len(metadatas) else {}
        filtered_meta = {k: v for k, v in meta.items() if k not in ["raw_json"]}
        context.append(f"--- Chunk {i+1} ---\n{chunk}\nMetadata: {filtered_meta}")

    context_str = "\n\n".join(context[:TOP_K])
    print("[Context str] Context prep: ", context_str)
    end = time.perf_counter()
    print(f"[TIMER] Context prep: {(end - start) * 1000:.2f} ms")

    prompt = f"""
    You are a **Property RAG Assistant**. 
    Your role is to answer user questions about property management using ONLY the retrieved context provided. 

    ### Instructions:
    -If the user greets you, respond with a friendly greeting.
    - Use the retrieved context as the sole source of truth. 
    - If the answer cannot be found in the context, reply exactly: "I don’t know based on available data."
    - Do not invent or assume information not present in the context.
    - Provide the answer in a clear, complete sentence (or short paragraph if needed).
    - If multiple chunks contain relevant details, synthesize them into a single coherent answer.

    ### Question:
    {user_query}

    ### Retrieved Context:
    {context_str}

    ### Final Answer:
    """
    if assigned_units:
        prompt += f"\n[EXTRA INFO] Relevant units: {', '.join(assigned_units)}"

    prompt += "\n\n[FINAL ANSWER]"
    response = generate_answer_with_ollama(prompt)

    if return_results:
        return context_str, response, results
    else:
        return context_str, response, None

def hybrid_generate_answer(user_query: str):
    unit_match = re.search(r"\bU-\d{3}\b", user_query, re.IGNORECASE)
    target_unit = unit_match.group().upper() if unit_match else None

    if target_unit and target_unit in FAST_CACHE:
        return f"Fast path: {target_unit} info → {FAST_CACHE[target_unit]}"

    print("[INFO] Falling back to RAG + LLM (slow path)…")
    results, collection_name, assigned_units = retrieve_chunks(user_query)
    context_str, response, _ = generate_answer(user_query, results, collection_name, assigned_units, return_results=True)
    return response

if __name__ == "__main__":
    DEBUG_MODE = True
    print("[INFO] Property RAG assistant running…")
    while True:
        user_query = input("Ask me about your property data: ")
        if user_query.lower() in ["exit", "quit"]:
            break

        total_start = time.perf_counter()
        response = hybrid_generate_answer(user_query)
        total_end = time.perf_counter()
        total_elapsed = (total_end - total_start) * 1000

        print("\n[FINAL ANSWER]\n", response)
        print(f"[TIMER] TOTAL query time: {total_elapsed:.2f} ms")

        if DEBUG_MODE:
            results_debug, collection_name_debug, assigned_units_debug = retrieve_chunks(user_query)
            context_str_debug, _, _ = generate_answer(
                user_query, results_debug, collection_name_debug, assigned_units_debug, return_results=True
            )
            print("\n[DEBUG] Retrieved Chunks:\n", context_str_debug)
