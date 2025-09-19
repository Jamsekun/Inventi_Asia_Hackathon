## testing only might delete later

import os
from motor.motor_asyncio import AsyncIOMotorClient

# Read from environment variables, with optional defaults
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "MockPropDB")

client = AsyncIOMotorClient(MONGODB_URI)
db = client[MONGODB_DB]