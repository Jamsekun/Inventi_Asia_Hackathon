# check_vector_db.py
import os
from dotenv import load_dotenv
import chromadb

load_dotenv()

CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")

# Load Chroma persistent client
client = chromadb.PersistentClient(path=CHROMA_DIR)

collections = client.list_collections()

if not collections:
    print("No collections found in the vector database.")
else:
    for col_obj in collections:
        col_name = col_obj.name
        col = client.get_or_create_collection(col_name)

        # Use include argument to make sure we get documents, metadatas, embeddings
        data = col.get(include=['documents', 'metadatas', 'embeddings'])

        num_docs = len(data['documents'])
        num_embeddings = len(data['embeddings'])
        print(f"\nCollection '{col_name}':")
        print(f"  Number of documents: {num_docs}")
        print(f"  Number of embeddings: {num_embeddings}")

        if num_docs == 0:
            print("  [WARN] Collection is empty!")
            continue

        # Print up to 5 sample documents and metadata
        print("  Sample documents and metadata:")
        for i, (doc, meta) in enumerate(zip(data['documents'], data['metadatas'])):
            if i >= 5:
                break
            print(f"    Document {i+1}: {doc}")
            print(f"    Metadata {i+1}: {meta}")
            print("    -----")
