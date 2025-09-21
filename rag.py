# query_rag.py
import os
import re
import json
from dotenv import load_dotenv
import chromadb
import torch
from sentence_transformers import SentenceTransformer
import ollama

load_dotenv()

# --- Config ---
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")
TOP_K = 3

# --- Init Clients ---
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INFO] Using device for embeddings: {device}")

embedder = SentenceTransformer(
    "sentence-transformers/all-mpnet-base-v2",
    device=device
)

try:
    client = chromadb.PersistentClient(path=CHROMA_DIR)
except Exception as e:
    raise RuntimeError(f"[ERROR] Failed to initialize Chroma client: {e}")


def generate_answer_with_ollama(prompt: str):
    """
    Generate answer using Ollama GPU model and return only the text.
    Includes error handling and fallback.
    """
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.message.content if response and response.message else "[ERROR] No response from Ollama."
    except Exception as e:
        return f"[ERROR] Ollama call failed: {e}"


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

# --- Helper Functions ---

def expand_query(user_query: str) -> list[str]:
    """
    Expand shorthand queries like U-203 into richer phrases,
    and add light semantic variations for better recall.
    """
    expansions = [user_query]

    # Unit shorthand (U-203 → Unit U-203, Apartment U-203, etc.)
    match = re.search(r"\bU-\d{3}\b", user_query, re.IGNORECASE)
    if match:
        unit_id = match.group().upper()
        expansions.extend([f"Unit {unit_id}", f"Apartment {unit_id}", f"Property {unit_id}"])

    # Add common synonyms for "rent", "tenant", etc. (basic expansion)
    if "rent" in user_query.lower():
        expansions.extend(["lease", "rental fee", "monthly rent"])
    if "tenant" in user_query.lower():
        expansions.extend(["occupant", "resident", "renter"])

    return list(sorted(set(expansions)))  # ensure uniqueness


def detect_collections(user_query: str) -> list[str]:
    """
    Return a list of relevant collections based on keywords.
    Uses regex matching with fallback.
    """
    q = user_query.lower()
    selected = []

    sorted_collections = sorted(
        COLLECTION_KEYWORDS.items(),
        key=lambda x: -max(len(k) for k in x[1])
    )

    for coll_name, keywords in sorted_collections:
        for k in keywords:
            if re.search(rf"\b{re.escape(k.lower())}\b", q):
                if coll_name not in selected:
                    selected.append(coll_name)
                break

    if not selected:
        selected = ["Units"]  # fallback

    return selected


def average_embeddings(embeddings: list[list[float]]) -> list[float]:
    """Take average of multiple embeddings (simple but safe)."""
    return [sum(vals) / len(vals) for vals in zip(*embeddings)]


def retrieve_chunks(user_query: str):
    expanded_queries = expand_query(user_query)
    target_collections = detect_collections(user_query)

    all_results = []
    all_assigned_units = []

    for target_collection in target_collections:
        try:
            collection = client.get_collection(target_collection)
        except Exception as e:
            print(f"[WARN] Failed to access collection {target_collection}: {e}")
            continue

        # Embed expanded queries
        query_embeddings = []
        for q in expanded_queries:
            try:
                query_embeddings.append(embedder.encode(q).tolist())
            except Exception as e:
                print(f"[WARN] Embedding failed for '{q}': {e}")

        if not query_embeddings:
            continue

        final_query_embedding = average_embeddings(query_embeddings)

        try:
            results = collection.query(
                query_embeddings=[final_query_embedding],
                n_results=TOP_K
            )
        except Exception as e:
            print(f"[WARN] Query failed on {target_collection}: {e}")
            continue

        # Special handling for Amenities
        if target_collection == "Amenities":
            assigned_units = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                raw = results["metadatas"][0][i].get("raw_json") if i < len(results["metadatas"][0]) else None
                if raw:
                    try:
                        amenity_doc = json.loads(raw)
                        if any(k.lower() in user_query.lower() for k in [amenity_doc.get("name", "")]):
                            assigned_units.extend(amenity_doc.get("assigned_units", []))
                    except json.JSONDecodeError:
                        print("[WARN] Malformed JSON in metadata, skipping...")
            assigned_units = list(sorted(set(assigned_units)))
            all_assigned_units.extend(assigned_units)

        all_results.append(results)

    return all_results, target_collections, list(sorted(set(all_assigned_units)))


def generate_answer(user_query: str, results=None, collection_name: str = None, assigned_units=None, return_results=False):
    """
    Generates an answer using Ollama and optionally returns raw results.
    If `results` is None, it retrieves chunks from the RAG system.
    """
    if results is None:
        results, target_collections, assigned_units = retrieve_chunks(user_query)

    # Flexible results parsing
    if isinstance(results, dict):
        chunks = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
    elif isinstance(results, list) and results:
        chunks = results[0].get("documents", [[]])[0] if "documents" in results[0] else results[0].get("documents", [])
        metadatas = results[0].get("metadatas", [[]])[0] if "metadatas" in results[0] else [{} for _ in chunks]
    else:
        chunks = []
        metadatas = []

    context = []
    for i, chunk in enumerate(chunks):
        meta = metadatas[i] if i < len(metadatas) else {}
        context.append(f"--- Chunk {i+1} (from {collection_name}) ---\n{chunk}\nMetadata: {meta}")

    context_str = "\n\n".join(context)

    # Build prompt
    prompt = f"""
You are a **Property RAG Assistant**.
Answer the question strictly using the retrieved context.
If the answer is not found, reply: "I don’t know based on available data."

[QUESTION]
{user_query}

[RETRIEVED CONTEXT]
{context_str}
"""
    if assigned_units:
        prompt += f"\n[EXTRA INFO] Relevant units: {', '.join(assigned_units)}"

    prompt += "\n\n[FINAL ANSWER]"

    response = generate_answer_with_ollama(prompt)

    if return_results:
        return context_str, response, results
    else:
        return context_str, response


if __name__ == "__main__":
    print("[INFO] Property RAG assistant running…")
    while True:
        user_query = input("Ask me about your property data: ")
        if user_query.lower() in ["exit", "quit"]:
            break

        results, collection_name, assigned_units = retrieve_chunks(user_query)
        context_str, response = generate_answer(user_query, results, collection_name, assigned_units)

        print("\n[RETRIEVED CHUNKS]\n")
        print(context_str)
        print("\n[FINAL ANSWER]\n", response)