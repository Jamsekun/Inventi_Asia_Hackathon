import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# List all collections
collections = db.list_collection_names()
print(f"Found {len(collections)} collections in database '{MONGO_DB}':\n")
for coll_name in collections:
    print(f"Collection: {coll_name}")
    
    collection = db[coll_name]
    
    # Fetch all documents in the collection
    docs = list(collection.find({}, {"_id": 1, "text": 1}))  # automatically get '_id' and 'text'
    
    print(f"  Total documents: {len(docs)}")
    if docs:
        print("  Sample documents:")
        for d in docs[:5]:  # show first 5 documents
            print(f"    {d}")
    else:
        print("  No documents found.")
    print("-" * 40)
