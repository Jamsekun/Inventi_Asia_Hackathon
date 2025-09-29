import os
import re
import json
import time
import math
from dotenv import load_dotenv
import chromadb
import torch
from sentence_transformers import SentenceTransformer
import ollama
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Optional, Union, List
import requests
from datetime import datetime
from urllib.parse import quote_plus

# load env
load_dotenv()

# debug
DEBUG_MODE = True

# --- Config ---
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3-mini")
TOP_K = int(os.getenv("TOP_K", "2"))

# API config for your FastAPI app
API_BASE = os.getenv("PROPERTY_API_BASE", "http://localhost:8000")
API_TIMEOUT = float(os.getenv("PROPERTY_API_TIMEOUT", "60"))

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
    "Amenities": ["pool", "gym", "facility", "facilities", "amenity", "recreation", "assigned units", "swimming"],
    "Maintenance": ["issue", "repair", "broken", "clogged", "maintenance", "status", "request", "fix"],
    "Contracts": ["contract", "lease", "rent agreement", "deposit", "start date", "end date", "monthly rent"],
    "Rent": ["rent", "payment", "paid", "unpaid", "due", "month"],
    "ElecBill": ["electricity", "elec", "bill", "power", "paid", "unpaid"],
    "WaterBill": ["water", "bill", "paid", "unpaid"],
    "Expenses": ["expense", "cost", "category", "amount", "date", "repair", "maintenance"],
    "Staff": ["staff", "employee", "worker", "assigned", "role", "contact"]
}

FAST_CACHE = {}  # Optional: populate elsewhere; used for hot unit lookups

# --- Ollama wrapper ---
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

# --- Embedding cache ---
@lru_cache(maxsize=1024)
def cached_embedding(text: str):
    with torch.inference_mode():
        return embedder.encode(text, convert_to_numpy=True).tolist()

# --- Query expansion ---
def expand_query(user_query: str) -> List[str]:
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

# --- Collection detection ---
def detect_collections(user_query: str) -> List[str]:
    q = user_query.lower()
    selected = []
    for coll_name, keywords in COLLECTION_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(k.lower())}\b", q) for k in keywords):
            selected.append(coll_name)
    return selected or ["Units"]

# --- Average embeddings ---
def average_embeddings(embeddings: List[List[float]]) -> List[float]:
    if not embeddings:
        return []
    return [sum(vals) / len(vals) for vals in zip(*embeddings)]

# --- Retrieval from Chroma (used as semantic router / selection) ---
def retrieve_chunks(user_query: str):
    expanded_queries = expand_query(user_query)
    target_collections = detect_collections(user_query)
    unit_match = re.search(r"\bU-\d{3}\b", user_query, re.IGNORECASE)
    target_unit = unit_match.group().upper() if unit_match else None

    # Timing embeddings
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
                query_embeddings=[final_query_embedding] if final_query_embedding else None,
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
                    # parse assigned_units from raw_json if present
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

    return results_list, target_collections, list(sorted(set(all_assigned_units))), target_unit

# --- REST helpers & extractors (to call your FastAPI endpoints) ---
def extract_unit_id(text: str) -> Optional[str]:
    m = re.search(r"\bU-\d{3}\b", text, re.IGNORECASE)
    return m.group().upper() if m else None

def extract_amenity_id(text: str) -> Optional[str]:
    m = re.search(r"\bA-\d{3}\b", text, re.IGNORECASE)
    if m:
        return m.group().upper()
    return None

def extract_tenant_id(text: str) -> Optional[str]:
    m = re.search(r"\bT-\d{3}\b", text, re.IGNORECASE)
    return m.group().upper() if m else None

def extract_bill_id(text: str) -> Optional[str]:
    m = re.search(r"\bBILL[-_ ]?\d+\b", text, re.IGNORECASE)
    return m.group() if m else None

def extract_month(text: str) -> Optional[str]:
    m = re.search(r"\b(20\d{2}-\d{2})\b", text)
    if m:
        return m.group(1)
    if "this month" in text.lower():
        return datetime.now().strftime("%Y-%m")
    return None

def sanitize_q(q: str) -> str:
    return quote_plus(q.strip())

# --- Build API jobs based on collections & heuristics ---
def build_api_jobs(user_query: str, target_collections: List[str], assigned_units: List[str], target_unit: Optional[str]):
    jobs = []
    q = user_query.lower()

    def add(path, params=None, coll_tag=None):
        url = f"{API_BASE.rstrip('/')}{path}"
        jobs.append((coll_tag or path, url, params or {}))

    if not target_unit:
        target_unit = extract_unit_id(user_query)

    for coll in target_collections:
        if coll == "Units":
            add("/units/summary/", coll_tag="UnitsSummary")
            if target_unit:
                add(f"/units/{target_unit}", coll_tag="Unit")
                add(f"/units/{target_unit}/tenant", coll_tag="UnitTenant")
                add(f"/units/{target_unit}/bills", coll_tag="UnitBills")
                add(f"/units/{target_unit}/maintenance", coll_tag="UnitMaintenance")
                add(f"/units/{target_unit}/amenities", coll_tag="UnitAmenities")

        elif coll == "Tenants":
            add("/tenants/", coll_tag="Tenants")
            t_id = extract_tenant_id(user_query)
            if t_id:
                add(f"/tenants/{t_id}", coll_tag="Tenant")
                add(f"/tenants/{t_id}/contract", coll_tag="TenantContract")
                add(f"/tenants/{t_id}/bills", coll_tag="TenantBills")
                add(f"/tenants/{t_id}/rent", coll_tag="TenantRent")
                add(f"/tenants/{t_id}/maintenance", coll_tag="TenantMaintenance")
            elif target_unit:
                add(f"/tenants/unit/{target_unit}", coll_tag="TenantByUnit")
            else:
                add(f"/tenants/search/", params={"q": user_query}, coll_tag="TenantSearch")

        elif coll == "Amenities":
            a_id = extract_amenity_id(user_query)
            if a_id:
                add(f"/amenities/{a_id}", coll_tag="Amenity")
            elif target_unit:
                add(f"/amenities/units/{target_unit}", coll_tag="AmenitiesForUnit")
            else:
                add("/amenities/", coll_tag="Amenities")
                add("/amenities/search/", params={"q": user_query}, coll_tag="AmenitySearch")

        elif coll == "Maintenance":
            add("/maintenance/summary/", coll_tag="MaintenanceSummary")
            add("/maintenance/pending/", coll_tag="MaintPending")
            add("/maintenance/resolved/", coll_tag="MaintResolved")
            if target_unit:
                add(f"/maintenance/unit/{target_unit}", coll_tag="MaintenanceForUnit")

        elif coll == "Contracts":
            add("/contracts/", coll_tag="Contracts")
            add("/contracts/expiring/", coll_tag="ContractsExpiring")
            t_id = extract_tenant_id(user_query)
            if t_id:
                add(f"/contracts/tenant/{t_id}", coll_tag="ContractByTenant")

        elif coll in ("Rent",):
            add("/rent/summary/monthly", coll_tag="RentMonthly")
            add("/rent/unpaid/", coll_tag="RentUnpaid")
            if target_unit:
                add(f"/rent/unit/{target_unit}", coll_tag="RentForUnit")
                month = extract_month(user_query)
                if month:
                    add(f"/rent/unit/{target_unit}/month/{month}", coll_tag="RentUnitMonth")
            t_id = extract_tenant_id(user_query)
            if t_id:
                add(f"/rent/tenant/{t_id}", coll_tag="RentByTenant")

        elif coll in ("ElecBill", "WaterBill"):
            add("/bills/summary/", coll_tag="BillsSummary")
            add("/bills/electric/", coll_tag="ElectricBills")
            add("/bills/water/", coll_tag="WaterBills")
            b_id = extract_bill_id(user_query)
            if b_id:
                add(f"/bills/electric/{b_id}", coll_tag="ElectricBill")
                add(f"/bills/water/{b_id}", coll_tag="WaterBill")
            if target_unit:
                add(f"/bills/unit/{target_unit}", coll_tag="BillsForUnit")

        elif coll == "Expenses":
            add("/expenses/summary/by-category", coll_tag="ExpensesByCategory")
            add("/expenses/", coll_tag="Expenses")
            add("/expenses/categories/", coll_tag="ExpenseCategories")

        elif coll == "Staff":
            add("/staff/summary/", coll_tag="StaffSummary")
            add("/staff/roles/", coll_tag="StaffRoles")
            m = re.search(r"\brole[: ]+([a-zA-Z0-9_ -]+)\b", user_query, re.IGNORECASE)
            if m:
                role = m.group(1)
                add(f"/staff/role/{quote_plus(role)}", coll_tag="StaffByRole")

        else:
            # fallback endpoints
            add("/summary", coll_tag="PropertySummary")
            add("/summary/bills", coll_tag="BillsSummaryLegacy")

    # Always include property summary and bills summary as relevant fallbacks
    add("/summary", coll_tag="PropertySummary")
    add("/bills/summary/", coll_tag="BillsSummary")

    # Include assigned_units context (from Amenities metadata)
    for u in (assigned_units or []):
        add(f"/units/{u}", coll_tag=f"Unit_{u}")
        add(f"/units/{u}/bills", coll_tag=f"UnitBills_{u}")

    return jobs
# Replace your existing fetch_realtime_context with this safer version

def safe_get(session, url, params=None, headers=None, retries=2, backoff_base=1.0):
    """GET with retries + exponential backoff. Returns parsed JSON or {'error': ...}."""
    headers = headers or {"Accept": "application/json"}
    params = params or {}
    last_exc = None
    for attempt in range(retries + 1):
        try:
            t0 = time.perf_counter()
            r = session.get(url, params=params, headers=headers, timeout=API_TIMEOUT)
            elapsed = (time.perf_counter() - t0)
            try:
                r.raise_for_status()
                payload = r.json()
            except Exception:
                # try to read text as fallback
                payload = {"error": f"status={r.status_code}", "text": r.text[:1000]}
            # return the payload and timing info
            return {"ok": True, "payload": payload, "elapsed": elapsed, "status_code": r.status_code}
        except Exception as e:
            last_exc = e
            # if last attempt, return error
            if attempt == retries:
                return {"ok": False, "error": str(e)}
            # exponential backoff
            sleep_for = backoff_base * (2 ** attempt)
            time.sleep(sleep_for)
    # fallback
    return {"ok": False, "error": str(last_exc)}

def fetch_realtime_context(user_query: str, target_collections: List[str], assigned_units: List[str], target_unit: Optional[str] = None, max_items=4) -> str:
    """
    Safer realtime fetch:
    - Uses safe_get (retries + backoff)
    - Limits number of endpoints fetched (max_items)
    - Reduces parallelism to avoid overloading backend
    - Logs elapsed times for each endpoint (helpful to debug slow endpoints)
    """
    session = requests.Session()
    headers = {"Accept": "application/json"}
    jobs = build_api_jobs(user_query, target_collections, assigned_units, target_unit)

    # dedupe
    seen = set()
    dedup_jobs = []
    for coll_tag, url, params in jobs:
        key = (url, tuple(sorted((params or {}).items())))
        if key in seen:
            continue
        seen.add(key)
        dedup_jobs.append((coll_tag, url, params))

    results = []

    # Lower concurrency: fewer workers so backend isn't hammered
    max_workers = 3
    # Also cap how many endpoints we try this query
    jobs_to_run = dedup_jobs[:max_items]

    def _worker(job):
        coll_tag, url, params = job
        start = time.perf_counter()
        res = safe_get(session, url, params=params, headers=headers, retries=2, backoff_base=1.0)
        wall = (time.perf_counter() - start)
        if res.get("ok"):
            payload = res["payload"]
            elapsed = res.get("elapsed", wall)
            results.append((coll_tag, url, payload, elapsed))
            print(f"[FETCH] {coll_tag} {url} OK in {elapsed:.2f}s")
        else:
            results.append((coll_tag, url, {"error": res.get("error")}, wall))
            print(f"[FETCH] {coll_tag} {url} ERROR after {wall:.2f}s -> {res.get('error')}")

    # run in threadpool but with controlled worker count
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_worker, job) for job in jobs_to_run]
        for f in as_completed(futures):
            pass  # workers append to results

    # Build compact context string
    ctx_parts = []
    for coll_tag, url, payload, elapsed in results:
        try:
            body = json.dumps(payload, indent=2, default=str)
        except Exception:
            body = str(payload)
        ctx_parts.append(f"--- SOURCE: {coll_tag} ({url}) ---\n#elapsed: {elapsed:.2f}s\n{body}")

    context_str = "\n\n".join(ctx_parts) if ctx_parts else ""
    return context_str

# --- generate_answer (uses realtime context from API; optional short chroma snippet) ---
def generate_answer(user_query: str, results=None, collection_name: Optional[Union[str, List[str]]] = None, assigned_units=None, return_results=True):
    # If results not provided, run retrieve_chunks to get routing info
    if results is None:
        results, target_collections, assigned_units, target_unit = retrieve_chunks(user_query)
    else:
        # if caller supplied results, still need to compute routing and target_unit
        _, target_collections, assigned_units, target_unit = retrieve_chunks(user_query)

    # Build short chroma snippet (TOP_K documents) for hybrid mode (optional)
    chunks = []
    metadatas = []
    if results:
        for r in results:
            docs = r.get("documents", [[]])[0]
            metas = r.get("metadatas", [[]])[0]
            chunks.extend(docs)
            metadatas.extend(metas)
    chroma_context = "\n\n".join([f"--- Chunk {i+1} ---\n{chunks[i]}\nMetadata: { {k:v for k,v in (metadatas[i] if i < len(metadatas) else {}).items() if k != 'raw_json'} }" for i in range(min(len(chunks), TOP_K))]) if chunks else ""

    # Fetch realtime context via your API
    realtime_context = fetch_realtime_context(user_query, target_collections, assigned_units, target_unit)

    # Prefer realtime_context; attach chroma snippet as supplemental
    if realtime_context:
        context_str = realtime_context
        if chroma_context:
            context_str += "\n\n--- SEMANTIC MATCHES (short) ---\n" + chroma_context
    else:
        context_str = chroma_context

    print("[Context str] Context prep (final): ", (context_str[:1000] + "...") if len(context_str) > 1000 else context_str)
    print("[User Query] Context prep (final): ", (user_query[:1000] + "...") if len(user_query) > 1000 else user_query)

    # Build the prompt (using the user's edited prompt)
    prompt = f"""
You are a **Property RAG Assistant**. 
Your role is to answer user questions about property management using ONLY the retrieved context provided. 

### Instructions:
-If the user greets you, respond with a friendly greeting.
- produce a well-formed list; do not append extra garbled text, remove the \n - 
- Use the retrieved context as the sole source of truth. 
- If the answer cannot be found in the context, reply exactly: "I don’t know based on available data."
- 

### Question:
{user_query}

### Retrieved Context:
{context_str}

### Generate Final Answer, remove unnecessary json formatting:
"""
    # Extra info about assigned units if present
    if assigned_units:
        prompt += f"\n[EXTRA INFO] Relevant units: {', '.join(assigned_units)}"

    prompt += "\n\n[FINAL ANSWER]"

    response = generate_answer_with_ollama(prompt)

    if return_results:
        return context_str, response, results
    else:
        return context_str, response, None

# --- hybrid_generate_answer: fast cache (unit) then fallback to RAG + LLM ---
def hybrid_generate_answer(user_query: str):
    unit_match = re.search(r"\bU-\d{3}\b", user_query, re.IGNORECASE)
    target_unit = unit_match.group().upper() if unit_match else None

    if target_unit and target_unit in FAST_CACHE:
        return f"Fast path: {target_unit} info → {FAST_CACHE[target_unit]}"

    print("[INFO] Falling back to RAG + LLM (slow path)…")
    # retrieve_chunks once and reuse results to avoid duplicate queries
    results, collection_name, assigned_units, target_unit = retrieve_chunks(user_query)
    context_str, response, _ = generate_answer(user_query, results=results, collection_name=collection_name, assigned_units=assigned_units, return_results=True)
    return response

# --- CLI main loop ---
if __name__ == "__main__":
    DEBUG_MODE = True
    print("[INFO] Property RAG assistant running…")
    try:
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
                # reuse retrieve_chunks once to avoid double work (we already called it in hybrid_generate_answer)
                results_debug, collection_name_debug, assigned_units_debug, target_unit_debug = retrieve_chunks(user_query)
                context_str_debug, _, _ = generate_answer(
                    user_query, results=results_debug, collection_name=collection_name_debug, assigned_units=assigned_units_debug, return_results=True
                )
                print("\n[DEBUG] Retrieved Chunks / Realtime Context (truncated):\n", (context_str_debug[:2000] + "...") if len(context_str_debug) > 2000 else context_str_debug)
    except KeyboardInterrupt:
        print("\n[INFO] Exiting.")
