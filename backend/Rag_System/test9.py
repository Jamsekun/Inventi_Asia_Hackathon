import certifi
from pymongo import MongoClient

MONGO_URI = "mongodb+srv://embedder:s5C41DCsElcfLIL5@infinitycondodb.uu7dwfs.mongodb.net/?retryWrites=true&w=majority&appName=InfinityCondoDB&authSource=admin"

DB_NAME = "InfinityCondoDB"

try:
    client = MongoClient(
        MONGO_URI,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000  # 5 sec timeout
    )
    db = client[DB_NAME]
    print("✅ Connected! Collections:", db.list_collection_names())
except Exception as e:
    print("❌ Connection failed:", e)
