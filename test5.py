import os
from dotenv import load_dotenv
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
import chromadb

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")
CHROMA_DIR = os.getenv("CHROMA_DIR")

# 1️⃣ Connect to MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

# 2️⃣ Initialize embedding model
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

# 3️⃣ Initialize Chroma persistent client
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)

# 4️⃣ Process each collection
collections = db.list_collection_names()
for coll_name in collections:
    print(f"\nProcessing collection: {coll_name}")
    collection = db[coll_name]
    
    # Fetch all documents
    docs = list(collection.find({}, {"_id": 1, "text": 1}))
    if not docs:
        print("  No documents found, skipping...")
        continue

    # Prepare lists for Chroma
    doc_texts = []
    doc_ids = []

    for doc in docs:
        text = doc.get("text", None)
        if text:  # skip empty texts
            doc_texts.append(text)
            doc_ids.append(str(doc["_id"]))

    if not doc_texts:
        print("  No valid texts to embed, skipping...")
        continue

    # Generate embeddings
    embeddings = embed_model.encode(doc_texts).tolist()

    # Add to Chroma
    col = chroma_client.get_or_create_collection(coll_name)
    col.add(
        documents=doc_texts,
        embeddings=embeddings,
        ids=doc_ids
    )

    print(f"  Added {len(doc_texts)} documents to Chroma collection '{coll_name}'")
