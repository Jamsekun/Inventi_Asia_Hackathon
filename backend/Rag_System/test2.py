from pymongo import MongoClient
from urllib.parse import quote_plus

username = "embedder"
password = quote_plus("8wRVaszmJnM3TKGS")  # encode special characters
MONGO_URI = f"mongodb+srv://{username}:{password}@infinitycondodb.uu7dwfs.mongodb.net/?retryWrites=true&w=majority&authSource=admin"

# Create the client
client = MongoClient(MONGO_URI)

# Access the database
db = client["MockPropDB"]

# List collections
print(db.list_collection_names())
