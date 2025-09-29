# index2.py (improved indexer)
import os
import json
import shutil
import re
import time
from typing import List, Dict, Any, Optional

from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
import chromadb
from dotenv import load_dotenv

# === CONFIG ===
# Point to your .env explicitly (keep this or change to your desired path)
dotenv_path = r"C:\James_folder\embedded_projects\Thesis_Clients\Hackathon_Folder\backend\.env"
load_dotenv(dotenv_path=dotenv_path)

MONGO_URI = os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGODB_DB", "MockPropDB")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")

# Rules file path (if you use it)
RULES_FILE = r"C:\James_folder\embedded_projects\Thesis_Clients\Hackathon_Folder\backend\Rag_System\rules.md"

# === CLEANUP previous chroma DB (optional) ===
if os.path.exists(CHROMA_DIR):
    try:
        shutil.rmtree(CHROMA_DIR)
        print(f"[CLEANUP] Deleted existing Chroma DB at {CHROMA_DIR}")
    except Exception as e:
        print(f"[WARN] Could not delete {CHROMA_DIR}: {e}")

# === Mongo connection ===
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI not set in env (.env).")
mc = MongoClient(MONGO_URI)
db = mc[MONGO_DB]

# === Embedding model init ===
# Use GPU if available
import torch
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INFO] Loading embedding model on device: {device}")
embed_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2", device=device)

# Warmup
with torch.inference_mode():
    _ = embed_model.encode(["warmup"])

# === Chroma client (persistent) ===
client = chromadb.PersistentClient(path=CHROMA_DIR)

# === Utilities ===
def normalize_text(s: Optional[str]) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()

def chunk_sentences(text: str, max_sentences=2) -> List[str]:
    """
    Break text into smaller chunks. We keep small context units (1-2 sentences).
    """
    text = normalize_text(text)
    if not text:
        return []
    # naive sentence split using punctuation; works for short doc fields
    parts = re.split(r'(?<=[\.\?\!])\s+', text)
    chunks = []
    for i in range(0, len(parts), max_sentences):
        chunk = " ".join(parts[i:i+max_sentences]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks

def embed_text(text: str) -> List[float]:
    """
    Produces an embedding for the text using the SentenceTransformer model.
    Returns a JSON-serializable list of floats.
    """
    text = normalize_text(text)
    if not text:
        return []
    with torch.inference_mode():
        emb = embed_model.encode([text], convert_to_numpy=True)[0]
    return emb.tolist()

# === API route mapper ===
# Based on the endpoints you provided earlier, produce a list of routes that are relevant
def map_api_routes_for_chunk(collection_name: str, doc: Any, chunk_meta: Dict[str, Any]) -> List[str]:
    """
    Return a list of API endpoint strings (concrete if IDs exist) relevant to this chunk.
    This helps the RAG runtime to fetch real-time data for the chunk.
    """
    routes = []
    # safe extract helpers
    def safe(k): return (doc.get(k) if isinstance(doc, dict) else None)

    # default fallbacks (top-level)
    if collection_name == "units":
        unit_id = safe("unit_id")
        if unit_id:
            routes.extend([
                f"/units/{unit_id}",
                f"/units/{unit_id}/tenant",
                f"/units/{unit_id}/bills",
                f"/units/{unit_id}/maintenance",
                f"/units/{unit_id}/amenities",
            ])
        routes.append("/units/summary/")
    elif collection_name == "amenities":
        amenity_id = safe("amenity_id") or safe("id") or None
        if amenity_id:
            routes.append(f"/amenities/{amenity_id}")
        # assigned units
        for u in safe("assigned_units") or []:
            routes.append(f"/amenities/units/{u}")
        routes.append("/amenities/")
        # search fallback
        name = safe("name")
        if name:
            routes.append(f"/amenities/search/?q={quote_plus_safe(name)}")
    elif collection_name in ("elecbill", "waterbill", "bills"):
        bill_id = safe("bill_id") or safe("id")
        unit_id = safe("unit_id")
        if bill_id:
            routes.append(f"/bills/electric/{bill_id}")  # we add both; caller can ignore 404s
            routes.append(f"/bills/water/{bill_id}")
        if unit_id:
            routes.append(f"/bills/unit/{unit_id}")
        routes.append("/bills/summary/")
    elif collection_name in ("rent",):
        rent_id = safe("bill_id") or safe("rent_id") or None
        unit_id = safe("unit_id")
        tenant_id = safe("tenant_id")
        if rent_id:
            routes.append(f"/rent/{rent_id}")
        if unit_id:
            routes.append(f"/rent/unit/{unit_id}")
            # monthly query as potential useful route
            routes.append(f"/rent/unit/{unit_id}/month/{extract_month_from_doc(doc) or 'current'}")
        if tenant_id:
            routes.append(f"/rent/tenant/{tenant_id}")
        routes.append("/rent/summary/monthly")
        routes.append("/rent/unpaid/")
    elif collection_name == "tenants":
        tenant_id = safe("tenant_id") or safe("_id")
        if tenant_id:
            routes.append(f"/tenants/{tenant_id}")
            routes.append(f"/tenants/{tenant_id}/contract")
            routes.append(f"/tenants/{tenant_id}/bills")
            routes.append(f"/tenants/{tenant_id}/rent")
            routes.append(f"/tenants/{tenant_id}/maintenance")
        if safe("unit_id"):
            routes.append(f"/tenants/unit/{safe('unit_id')}")
        routes.append("/tenants/")
        routes.append("/tenants/search/?q=" + quote_plus_safe(safe("name") or ""))
    elif collection_name in ("contracts",):
        contract_id = safe("contract_id") or safe("_id")
        if contract_id:
            routes.append(f"/contracts/{contract_id}")
        if safe("tenant_id"):
            routes.append(f"/contracts/tenant/{safe('tenant_id')}")
        routes.append("/contracts/expiring/")
        routes.append("/contracts/")
    elif collection_name in ("maintenance",):
        req_id = safe("request_id") or safe("_id")
        if req_id:
            routes.append(f"/maintenance/{req_id}")
        if safe("unit_id"):
            routes.append(f"/maintenance/unit/{safe('unit_id')}")
        routes.extend([
            "/maintenance/summary/",
            "/maintenance/pending/",
            "/maintenance/resolved/"
        ])
    elif collection_name in ("expenses",):
        exp_id = safe("expense_id") or safe("_id")
        if exp_id:
            routes.append(f"/expenses/{exp_id}")
        routes.extend([
            "/expenses/",
            "/expenses/categories/",
            "/expenses/summary/by-category"
        ])
    elif collection_name in ("staff",):
        staff_id = safe("staff_id") or safe("_id")
        if staff_id:
            routes.append(f"/staff/{staff_id}")
            routes.append(f"/staff/{staff_id}/assignments")
        roles = safe("role") or ""
        if roles:
            routes.append(f"/staff/role/{quote_plus_safe(roles)}")
        routes.extend(["/staff/summary/", "/staff/roles/"])
    elif collection_name == "rules":
        # rules are general system knowledge; point to property summary as useful fallback
        routes.append("/summary")
    else:
        # generic fallback for anything else
        routes.append("/summary")
        routes.append("/summary/bills")

    # dedupe while preserving order
    seen = set()
    deduped = []
    for r in routes:
        if r and r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped

# small helper functions used above
def quote_plus_safe(s: Optional[str]) -> str:
    from urllib.parse import quote_plus
    return quote_plus(str(s or ""))

def extract_month_from_doc(doc: Any) -> Optional[str]:
    # if doc stores month or date fields, try to format YYYY-MM
    if isinstance(doc, dict):
        for k in ("month", "period", "due_date", "date"):
            v = doc.get(k)
            if v:
                # try to find yyyy-mm
                m = re.search(r"(20\d{2}-\d{2})", str(v))
                if m:
                    return m.group(1)
    return None

# === chunking function (improved atomic chunks) ===
def chunk_doc_atomic(collection_name: str, doc: Any) -> List[Dict[str, Any]]:
    """
    Convert a MongoDB document into atomic chunks suitable for RAG.
    Each chunk includes `text`, `metadata` and `api_routes`.
    """
    chunks: List[Dict[str, Any]] = []

    # Helper to add chunk
    def add_chunk(text: str, metadata_extra: Optional[Dict[str, Any]] = None):
        base_id = None
        if isinstance(doc, dict):
            base_id = (
                doc.get("unit_id")
                or doc.get("amenity_id")
                or doc.get("tenant_id")
                or doc.get("contract_id")
                or str(doc.get("_id", collection_name))
            )
        else:
            base_id = collection_name

        idx = len(chunks) + 1
        chunk_id = f"{collection_name}-{base_id}-{idx}"
        metadata = {"collection": collection_name}
        if isinstance(doc, dict):
            try:
                metadata["raw_json"] = json.dumps(doc, default=str)
            except Exception:
                metadata["raw_json"] = str(doc)
        if metadata_extra:
            metadata.update(metadata_extra)

        # compute api routes for this chunk (important)
        metadata["api_routes"] = ", ".join(map_api_routes_for_chunk(collection_name, doc if isinstance(doc, dict) else {}, metadata))



        # preview text for easier debugging
        metadata["text_preview"] = normalize_text(text)[:400]

        chunks.append({
            "chunk_id": chunk_id,
            "text": normalize_text(text),
            "metadata": metadata
        })
        print(f"[CHUNK] {chunk_id} | collection={collection_name} | preview='{metadata['text_preview'][:80]}' | endpoints={metadata['api_routes'][:3]}")

    try:
        # RULES: special handling to split by headings and paragraphs
        if collection_name == "rules":
            if not os.path.exists(RULES_FILE):
                raise FileNotFoundError(f"Rules file not found at {RULES_FILE}")
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            sections = re.split(r"(?m)(^# .+?$|^## .+?$|^### .+?$)", content)
            current_heading = "General"
            for part in sections:
                if part.strip().startswith("#"):
                    current_heading = part.strip()
                elif part.strip():
                    for i, sentence in enumerate(re.split(r"(?<=[.!?]) +|\n- ", part)):
                        if sentence.strip():
                            add_chunk(sentence.strip(), {"section": current_heading, "field": f"rule-{i+1}"})

        # AMENITIES
        elif collection_name == "amenities" and isinstance(doc, dict):
            name = doc.get("name")
            if name:
                add_chunk(f"Amenity name: {name}", {"field": "name"})
            desc = doc.get("description", "")
            for i, c in enumerate(chunk_sentences(desc)):
                add_chunk(c, {"field": f"description-{i+1}"})
            add_chunk(f"Amenity availability: {doc.get('availability')}", {"field": "availability"})
            for unit in doc.get("assigned_units", []):
                add_chunk(f"Unit {unit} has access to this amenity.", {"field": "assigned_units", "unit_id": unit})

        # CONTRACTS
        elif collection_name == "contracts" and isinstance(doc, dict):
            add_chunk(f"Contract ID: {doc.get('contract_id')}", {"field": "contract_id"})
            add_chunk(f"Tenant: {doc.get('tenant_id')}", {"field": "tenant_id"})
            add_chunk(f"Unit: {doc.get('unit_id')}", {"field": "unit_id"})
            add_chunk(f"Monthly rent: {doc.get('monthly_rent')}", {"field": "monthly_rent"})
            add_chunk(f"Deposit: {doc.get('deposit')}", {"field": "deposit"})
            add_chunk(f"Status: {doc.get('status')}", {"field": "status"})

        # BILLS / RENT
        elif collection_name in {"elecbill", "waterbill", "bills", "rent"} and isinstance(doc, dict):
            # these are generic bill-like docs
            if doc.get("bill_id"):
                add_chunk(f"Bill ID: {doc.get('bill_id')}", {"field": "bill_id"})
            if doc.get("rent_id"):
                add_chunk(f"Rent ID: {doc.get('rent_id')}", {"field": "rent_id"})
            if doc.get("unit_id"):
                add_chunk(f"Unit: {doc.get('unit_id')}", {"field": "unit_id"})
            if doc.get("amount") is not None:
                add_chunk(f"Amount: {doc.get('amount')}", {"field": "amount"})
            if doc.get("due_date"):
                add_chunk(f"Due date: {doc.get('due_date')}", {"field": "due_date"})
            if doc.get("status"):
                add_chunk(f"Status: {doc.get('status')}", {"field": "status"})
            # include full short summary chunk
            summary = ", ".join([f"{k}: {v}" for k, v in doc.items() if k in ("bill_id", "unit_id", "amount", "due_date", "status")])
            if summary:
                add_chunk(f"Summary: {summary}", {"field": "summary"})

        # EXPENSES
        elif collection_name == "expenses" and isinstance(doc, dict):
            add_chunk(f"Expense ID: {doc.get('expense_id')}", {"field": "expense_id"})
            add_chunk(f"Category: {doc.get('category')}", {"field": "category"})
            add_chunk(f"Amount: {doc.get('amount')}", {"field": "amount"})
            add_chunk(f"Date: {doc.get('date')}", {"field": "date"})
            description = doc.get("description")
            if isinstance(description, str):
                for i, c in enumerate(chunk_sentences(description)):
                    add_chunk(c, {"field": f"description-{i+1}"})

        # MAINTENANCE
        elif collection_name == "maintenance" and isinstance(doc, dict):
            add_chunk(f"Maintenance request ID: {doc.get('request_id')}", {"field": "request_id"})
            add_chunk(f"Unit: {doc.get('unit_id')}", {"field": "unit_id"})
            for i, issue in enumerate(doc.get("issues", [])):
                add_chunk(f"Issue: {issue}", {"field": f"issue-{i+1}"})
            add_chunk(f"Status: {doc.get('status')}", {"field": "status"})

        # STAFF
        elif collection_name == "staff" and isinstance(doc, dict):
            add_chunk(f"Staff name: {doc.get('name')}", {"field": "name"})
            add_chunk(f"Role: {doc.get('role')}", {"field": "role"})
            add_chunk(f"Contact: {doc.get('contact')}", {"field": "contact"})

        # TENANTS
        elif collection_name == "tenants" and isinstance(doc, dict):
            add_chunk(f"Tenant name: {doc.get('name')}", {"field": "name"})
            add_chunk(f"Contact: {doc.get('contact')}", {"field": "contact"})
            add_chunk(f"Email: {doc.get('email')}", {"field": "email"})
            add_chunk(f"Unit: {doc.get('unit_id')}", {"field": "unit_id"})
            # small summary chunk
            add_chunk(f"Tenant summary: {doc.get('name')} - {doc.get('unit_id')}", {"field": "summary"})

        # UNITS
        elif collection_name == "units" and isinstance(doc, dict):
            add_chunk(f"Unit ID: {doc.get('unit_id')}", {"field": "unit_id"})
            add_chunk(f"Floor: {doc.get('floor')}", {"field": "floor"})
            add_chunk(f"Number: {doc.get('number')}", {"field": "number"})
            add_chunk(f"Status: {doc.get('status')}", {"field": "status"})
            if doc.get("tenant_id"):
                add_chunk(f"Tenant: {doc.get('tenant_id')}", {"field": "tenant_id"})

        else:
            # Generic fallback: convert fields into atomic chunks
            if isinstance(doc, dict):
                for k, v in doc.items():
                    if isinstance(v, (str, int, float)) and v:
                        for c in chunk_sentences(str(v)):
                            add_chunk(f"{k}: {c}", {"field": k})
                    elif isinstance(v, list):
                        for item in v:
                            add_chunk(f"{k}: {str(item)}", {"field": k})
                    else:
                        add_chunk(f"{k}: {str(v)}", {"field": k})
            else:
                add_chunk(str(doc), {"field": "raw_text"})

    except Exception as e:
        # graceful fallback: store the raw doc as a single chunk
        add_chunk(str(doc), {"field": "raw_text", "error": str(e)})

    return chunks

# === Upsert per-chunk to Chroma ===
def sync_record(collection_name: str, doc: Any):
    """
    Upsert the document's chunks into the Chroma collection named `collection_name`.
    """
    # create or get collection
    collection_client = client.get_or_create_collection(name=collection_name)
    chunks = chunk_doc_atomic(collection_name, doc)
    for chunk in chunks:
        text = chunk["text"]
        embedding = embed_text(text)
        metadata = chunk["metadata"]
        stable_id = chunk["chunk_id"]
        try:
            collection_client.upsert(
                ids=[stable_id],
                documents=[text],
                metadatas=[metadata],
                embeddings=[embedding]
            )
            print(f"[UPSERT] {stable_id} in {collection_name} | emb_len={len(embedding)}")
        except Exception as e:
            print(f"[ERROR] Upsert failed for {stable_id}: {e}")

def sync_collection(collection_name: str):
    coll = db[collection_name]
    print(f"[SYNC] Embedding documents in '{collection_name}'...")
    total = coll.count_documents({})
    cnt = 0
    for doc in coll.find():
        try:
            sync_record(collection_name, doc)
            cnt += 1
            if cnt % 50 == 0:
                print(f"[SYNC] Progress: {cnt}/{total}")
        except Exception as e:
            print(f"[WARN] Failed to sync record: {e}")
    print(f"[SYNC] Finished embedding '{collection_name}'. Processed {cnt} docs.")

if __name__ == "__main__":
    # index all collections in the DB
    for c in db.list_collection_names():
        sync_collection(c)
    print("Indexing complete. All existing collections are embedded in Chroma.")
