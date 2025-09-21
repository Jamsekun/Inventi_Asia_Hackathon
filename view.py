# view_chunks.py
import os
from dotenv import load_dotenv
import chromadb

load_dotenv()

CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")

# Load Chroma persistent client
client = chromadb.PersistentClient(path=CHROMA_DIR)

def view_all_chunks():
    print("\n[INFO] Listing all chunks from ChromaDB...\n")

    collections = client.list_collections()
    if not collections:
        print("⚠️ No collections found in ChromaDB.")
        return

    for col_obj in collections:
        col_name = col_obj.name
        print(f"\n=== Collection: {col_name} ===")
        col = client.get_collection(name=col_name)

        # ✅ Don't put "ids" in include — ids are always returned
        data = col.get(include=["documents", "metadatas"])

        if not data["documents"]:
            print("  ⚠️ No documents found in this collection.")
            continue

        for chunk_id, doc, metadata in zip(data["ids"], data["documents"], data["metadatas"]):
            print(f"\n--- Chunk {chunk_id} ---")  # rent1, amenities4, etc.
            print(doc)
            if metadata:
                print(f"Metadata: {metadata}")

if __name__ == "__main__":
    view_all_chunks()
