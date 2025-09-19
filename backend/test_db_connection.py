## testing only might delete later

import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

# Get MongoDB URI and DB name
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "MockPropDB")

async def test_connection():
    try:
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI is not set. Check your .env file or environment variables.")

        client = AsyncIOMotorClient(MONGODB_URI)
        await client.admin.command("ping")
        print("✅ Successfully connected to MongoDB Atlas!")

        # List databases
        dbs = await client.list_database_names()
        print("Databases:", dbs)

        # List collections in target DB
        db = client[MONGODB_DB]
        collections = await db.list_collection_names()
        print(f"Collections in '{MONGODB_DB}':", collections)

        # Check if ElecBill and WaterBill collections exist
        for name in ["ElecBill", "WaterBill"]:
            if name in collections:
                count = await db[name].count_documents({})
                print(f"✅ '{name}' collection found with {count} documents.")
            else:
                print(f"⚠️ '{name}' collection not found.")

    except Exception as e:
        print("❌ Connection failed:", e)

if __name__ == "__main__":
    asyncio.run(test_connection())
