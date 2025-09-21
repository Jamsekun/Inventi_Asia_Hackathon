# live_sync_chroma.py
import os
import json
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
import chromadb
from dotenv import load_dotenv
from threading import Thread

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "test")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")

# Connect MongoDB
mc = MongoClient(MONGO_URI)
db = mc[MONGO_DB]

# Load embedding model
emb_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

# Persistent Chroma client
client = chromadb.PersistentClient(path=CHROMA_DIR)

def embed_text(text: str):
    return emb_model.encode(text).tolist()

def text_from_doc(collection_name, doc):
    """Convert Mongo doc to human-readable sentence."""
    try:
        if collection_name == "amenities":
            return f"Amenity {doc.get('name')} (ID: {doc.get('amenity_id')}), description: {doc.get('description')}, available: {doc.get('availability')}, assigned units: {', '.join(doc.get('assigned_units', []))}."
        elif collection_name == "contracts":
            return f"Contract {doc.get('contract_id')} for tenant {doc.get('tenant_id')} in unit {doc.get('unit_id')}, rent: {doc.get('monthly_rent')}, deposit: {doc.get('deposit')}, status: {doc.get('status')}."
        elif collection_name in ["elecbill", "waterbill", "rent"]:
            return f"Bill {doc.get('bill_id')} for unit {doc.get('unit_id')}: amount {doc.get('amount')}, due {doc.get('due_date')}, status: {doc.get('status')}."
        elif collection_name == "expenses":
            return f"Expense {doc.get('expense_id')}, category: {doc.get('category')}, amount: {doc.get('amount')}, date: {doc.get('date')}, description: {doc.get('description')}."
        elif collection_name == "maintenance":
            return f"Maintenance request {doc.get('request_id')} for unit {doc.get('unit_id')}, issue: {doc.get('issue')}, status: {doc.get('status')}."
        elif collection_name == "staff":
            return f"Staff {doc.get('name')} (ID: {doc.get('staff_id')}), role: {doc.get('role')}, contact: {doc.get('contact')}."
        elif collection_name == "tenants":
            return f"Tenant {doc.get('name')} (ID: {doc.get('tenant_id')}), contact: {doc.get('contact')}, email: {doc.get('email')}, unit: {doc.get('unit_id')}."
        elif collection_name == "units":
            return f"Unit {doc.get('unit_id')} on floor {doc.get('floor')}, number: {doc.get('number')}, status: {doc.get('status')}, tenant: {doc.get('tenant_id')}."
        else:
            return json.dumps(doc, default=str)
    except Exception:
        return json.dumps(doc, default=str)

def sync_record(collection_name, doc):
    """Upsert a MongoDB record into Chroma."""
    collection_client = client.get_or_create_collection(name=collection_name)
    text = text_from_doc(collection_name, doc)
    embedding = embed_text(text)
    metadata = {"raw_json": json.dumps(doc, default=str)}
    for key in ["unit_id", "bill_id", "tenant_id", "status", "due_date", "amenity_id"]:
        value = doc.get(key)
        if value is not None:
            metadata[key] = str(value)
    stable_id = doc.get("unit_id") or doc.get("amenity_id") or doc.get("tenant_id") or str(doc.get("_id"))
    collection_client.upsert(
        ids=[stable_id],
        documents=[text],
        metadatas=[metadata],
        embeddings=[embedding]
    )
    print(f"[UPSERT] {stable_id} in {collection_name}")

def delete_record(collection_name, doc_id):
    """Remove a document from Chroma by its stable ID."""
    collection_client = client.get_or_create_collection(name=collection_name)
    collection_client.delete(ids=[doc_id])
    print(f"[DELETE] {doc_id} from {collection_name}")

def sync_all_existing(collection_name):
    """Embed all existing MongoDB documents in the collection."""
    coll = db[collection_name]
    print(f"[SYNC] Embedding existing documents in '{collection_name}'...")
    for doc in coll.find():
        sync_record(collection_name, doc)
    print(f"[SYNC] Finished embedding '{collection_name}'.")

def watch_collection(collection_name):
    """Listen to MongoDB changes and sync Chroma."""
    coll = db[collection_name]
    print(f"Watching collection: {collection_name}")
    with coll.watch(full_document='updateLookup') as stream:
        for change in stream:
            operation = change["operationType"]
            full_doc = change.get("fullDocument")
            doc_id = full_doc.get("unit_id") or full_doc.get("amenity_id") or full_doc.get("tenant_id") or str(full_doc.get("_id"))

            if operation in ["insert", "update", "replace"]:
                sync_record(collection_name, full_doc)
            elif operation == "delete":
                delete_record(collection_name, doc_id)

if __name__ == "__main__":
    # Sync all existing documents first
    for c in db.list_collection_names():
        sync_all_existing(c)

    # Then start live-watch threads
    for c in db.list_collection_names():
        t = Thread(target=watch_collection, args=(c,), daemon=True)
        t.start()

    print("Live-sync active. Listening for MongoDB changes...")
    try:
        while True:
            pass  # Keep main thread alive
    except KeyboardInterrupt:
        print("Stopping live-sync.")
