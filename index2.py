# indexer_once.py
import os
import json
import shutil
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
import chromadb
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "test")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")

# Remove existing Chroma DB if it exists
if os.path.exists(CHROMA_DIR):
    shutil.rmtree(CHROMA_DIR)
    print(f"[CLEANUP] Deleted existing Chroma DB at {CHROMA_DIR}")

# Connect MongoDB
mc = MongoClient(MONGO_URI)
db = mc[MONGO_DB]

# Load embedding model
emb_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

# Persistent Chroma client
client = chromadb.PersistentClient(path=CHROMA_DIR)

def embed_text(text: str):
    return emb_model.encode(text).tolist()

def chunk_doc_atomic(collection_name, doc):
    """
    Convert a MongoDB document into multiple small chunks suitable for RAG.
    Each chunk contains a single fact or atomic piece of information.
    Returns a list of chunks: [{"chunk_id": ..., "text": ..., "metadata": {...}}, ...]
    """
    chunks = []

    def add_chunk(text, metadata_extra=None):
        # Create a unique chunk id
        base_id = doc.get("unit_id") or doc.get("amenity_id") or doc.get("tenant_id") or str(doc.get("_id"))
        chunk_idx = len(chunks) + 1
        chunk_id = f"{collection_name}-{base_id}-{chunk_idx}"
        metadata = {"collection": collection_name, "raw_json": json.dumps(doc, default=str)}
        if metadata_extra:
            metadata.update(metadata_extra)
        chunks.append({
            "chunk_id": chunk_id,
            "text": text,
            "metadata": metadata
        })

    try:
        if collection_name == "amenities":
            # Name
            add_chunk(f"Amenity name: {doc.get('name')}", {"field": "name"})
            # Description (split long text into sentences)
            desc = doc.get("description", "")
            for i, sentence in enumerate(desc.split(". ")):
                if sentence.strip():
                    add_chunk(sentence.strip(), {"field": f"description-{i+1}"})
            # Availability
            add_chunk(f"Amenity availability: {doc.get('availability')}", {"field": "availability"})
            # Assigned units (split array into separate chunks)
            for unit in doc.get("assigned_units", []):
                add_chunk(f"Unit {unit} has access to this amenity.", {"field": "assigned_units", "unit_id": unit})

        elif collection_name == "contracts":
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
            add_chunk(f"Due date: {doc.get('due_date')}", {"field": "due_date"})
            add_chunk(f"Status: {doc.get('status')}", {"field": "status"})

        elif collection_name == "expenses":
            add_chunk(f"Expense ID: {doc.get('expense_id')}", {"field": "expense_id"})
            add_chunk(f"Category: {doc.get('category')}", {"field": "category"})
            add_chunk(f"Amount: {doc.get('amount')}", {"field": "amount"})
            add_chunk(f"Date: {doc.get('date')}", {"field": "date"})
            add_chunk(f"Description: {doc.get('description')}", {"field": "description"})

        elif collection_name == "maintenance":
            add_chunk(f"Maintenance request ID: {doc.get('request_id')}", {"field": "request_id"})
            add_chunk(f"Unit: {doc.get('unit_id')}", {"field": "unit_id"})
            # Split issues array
            for issue in doc.get("issues", []):
                add_chunk(f"Issue: {issue}", {"field": "issue"})
            add_chunk(f"Status: {doc.get('status')}", {"field": "status"})

        elif collection_name == "staff":
            add_chunk(f"Staff name: {doc.get('name')}", {"field": "name"})
            add_chunk(f"Role: {doc.get('role')}", {"field": "role"})
            add_chunk(f"Contact: {doc.get('contact')}", {"field": "contact"})

        elif collection_name == "tenants":
            add_chunk(f"Tenant name: {doc.get('name')}", {"field": "name"})
            add_chunk(f"Contact: {doc.get('contact')}", {"field": "contact"})
            add_chunk(f"Email: {doc.get('email')}", {"field": "email"})
            add_chunk(f"Unit: {doc.get('unit_id')}", {"field": "unit_id"})

        elif collection_name == "units":
            add_chunk(f"Unit ID: {doc.get('unit_id')}", {"field": "unit_id"})
            add_chunk(f"Floor: {doc.get('floor')}", {"field": "floor"})
            add_chunk(f"Number: {doc.get('number')}", {"field": "number"})
            add_chunk(f"Status: {doc.get('status')}", {"field": "status"})
            add_chunk(f"Tenant: {doc.get('tenant_id')}", {"field": "tenant_id"})

        else:
            # Fallback: split doc into key-value chunks
            for k, v in doc.items():
                add_chunk(f"{k}: {v}", {"field": k})

    except Exception:
        # In case of unexpected field formats
        for k, v in doc.items():
            add_chunk(f"{k}: {v}", {"field": k})

    return chunks

def sync_record(collection_name, doc):
    """Upsert a MongoDB record into Chroma with atomic chunks."""
    collection_client = client.get_or_create_collection(name=collection_name)
    chunks = chunk_doc_atomic(collection_name, doc)

    for chunk in chunks:
        text = chunk["text"]
        embedding = embed_text(text)
        metadata = chunk["metadata"]
        stable_id = chunk["chunk_id"]

        # Upsert each atomic chunk separately
        collection_client.upsert(
            ids=[stable_id],
            documents=[text],
            metadatas=[metadata],
            embeddings=[embedding]
        )

        # Print concise log
        print(f"[UPSERT] {stable_id} in {collection_name} | Embedding length: {len(embedding)} | first 5 values: {embedding[:5]}")


def sync_collection(collection_name):
    """Embed all existing MongoDB documents in the collection."""
    coll = db[collection_name]
    print(f"[SYNC] Embedding documents in '{collection_name}'...")
    for doc in coll.find():
        sync_record(collection_name, doc)
    print(f"[SYNC] Finished embedding '{collection_name}'.")

if __name__ == "__main__":
    for c in db.list_collection_names():
        sync_collection(c)
    print("Indexing complete. All existing collections are embedded in Chroma.")
