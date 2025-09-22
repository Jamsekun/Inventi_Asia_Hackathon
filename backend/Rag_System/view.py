# view_chunks.py
import os
from dotenv import load_dotenv
import chromadb

load_dotenv()

CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")

# Load Chroma persistent client
client = chromadb.PersistentClient(path=CHROMA_DIR)


def demo_add_and_query():
    """Add a sample chunk and run a query."""
    collection = client.get_or_create_collection(name="MyCollection")

    # Example embedding (replace with real embeddings from your model)
    embedding = [0.1, 0.2, 0.3]

    collection.add(
        documents=["This is a sample chunk."],
        embeddings=[embedding],
        metadatas=[{"source": "doc1", "chunk_id": "chunk1"}],
        ids=["chunk1"],
    )

    results = collection.query(
        query_embeddings=[embedding],
        n_results=5,
        where={"source": "doc1"},  # optional metadata filter
    )

    print("\n[INFO] Query results:")
    print(results)


def view_all_chunks():
    """List all chunks from all collections in ChromaDB."""
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

        for chunk_id, doc, metadata in zip(
            data["ids"], data["documents"], data["metadatas"]
        ):
            print(f"\n--- Chunk {chunk_id} ---")
            print(doc)
            if metadata:
                print(f"Metadata: {metadata}")

def view_rules_chunks():
    """List all chunks from the 'rules' collection in ChromaDB."""
    print("\n[INFO] Listing chunks from 'rules' collection...\n")

    try:
        col = client.get_collection(name="rules")
    except Exception as e:
        print(f"⚠️ Could not find 'rules' collection: {e}")
        return

    data = col.get(include=["documents", "metadatas"])

    if not data["documents"]:
        print("⚠️ No documents found in 'rules' collection.")
        return

    for chunk_id, doc, metadata in zip(
        data["ids"], data["documents"], data["metadatas"]
    ):
        print(f"\n--- Chunk {chunk_id} ---")
        print(doc)
        if metadata:
            print(f"Metadata: {metadata}")

if __name__ == "__main__":
    # demo_add_and_query()
    view_all_chunks()
    # view_rules_chunks()

    # Uncomment if you want to clean up afterwards
    # client.delete_collection(name="MyCollection")
