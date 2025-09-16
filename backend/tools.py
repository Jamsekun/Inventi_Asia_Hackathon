import os
from datetime import datetime
from .db import db

DEMO_OWNER_ID = os.getenv("DEMO_OWNER_ID", "owner_demo_1")

async def get_bills_summary(period: str):
    match = {"ownerId": DEMO_OWNER_ID}
    if period:
        match["period"] = period
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$period", "total": {"$sum": "$amount"},
                      "due_items": {"$sum": {"$cond": [{"$eq": ["$status", "due"]}, 1, 0]}}}},
        {"$project": {"_id": 0, "period": "$_id", "total_amount": "$total", "due_items": 1}},
        {"$limit": 1},
    ]
    docs = [d async for d in db.bills.aggregate(pipeline)]
    if docs:
        return docs[0]
    return {"period": period, "total_amount": 0.0, "due_items": 0}