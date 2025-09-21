import chromadb
from chromadb.config import Settings

# ✅ use PersistentClient (not Client)
client = chromadb.PersistentClient(
    path="./chroma_db"  # directory where Chroma stores data
)

# create or load a collection
collection = client.get_or_create_collection("test_collection")
print("Collection ready:", collection.name)
