
import os
from typing import List, Dict, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError, OperationFailure
import logging
from datetime import datetime
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.id_fields = {
            "Amenities": "amenity_id",
            "Contracts": "contract_id",
            "ElecBill": "bill_id",
            "Expenses": "expense_id",
            "Maintenance": "request_id",
            "Rent": "rent_id",
            "Staff": "staff_id",
            "Tenants": "tenant_id",
            "Units": "unit_id",
            "WaterBill": "bill_id",
        }
        
    async def connect(self):
        """Initialize database connection"""
        try:
            # Try to load from .env file first, then fall back to environment variables
            # Try multiple paths for .env file
            env_paths = [
                os.path.join(os.getcwd(), ".env"),
                os.path.join(os.path.dirname(__file__), ".env"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
            ]
            
            for env_path in env_paths:
                if os.path.exists(env_path):
                    load_dotenv(env_path)
                    logger.info(f"Loaded .env from: {env_path}")
                    break
            else:
                # No .env file found, try loading from current directory
                load_dotenv()
            
            mongodb_uri = os.getenv("MONGODB_URI")
            mongodb_db = os.getenv("MONGODB_DB", "MockPropDB")
            
            if not mongodb_uri:
                raise ValueError("MONGODB_URI is not set. Please set it in your environment variables or create a .env file.")
            
            self.client = AsyncIOMotorClient(mongodb_uri)
            self.db = self.client[mongodb_db]
            
            # Test connection
            await self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {mongodb_uri}/{mongodb_db}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    # Generic CRUD operations
    async def create_document(self, collection_name: str, document: Dict[str, Any]) -> str:
        """Create a new document in the specified collection"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            result = await self.db[collection_name].insert_one(document)
            return str(result.inserted_id)
        except DuplicateKeyError as e:
            raise ValueError(f"Document with this ID already exists: {e}")
        except Exception as e:
            raise Exception(f"Failed to create document: {e}")
    
    async def get_document(self, collection_name: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            from bson import ObjectId
            if ObjectId.is_valid(document_id):
                document = await self.db[collection_name].find_one({"_id": ObjectId(document_id)})
            else:
                # Use custom ID field from mapping or fallback
                id_field = self.id_fields.get(collection_name, f"{collection_name[:-1].lower()}_id")
                document = await self.db[collection_name].find_one({id_field: document_id})
            
            if document:
                document["_id"] = str(document["_id"])
            return document
        except Exception as e:
            raise Exception(f"Failed to get document: {e}")
    
    async def get_documents(
        self, 
        collection_name: str, 
        filter_dict: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 100,
        sort_field: Optional[str] = None,
        sort_order: int = 1
    ) -> List[Dict[str, Any]]:
        """Get multiple documents with optional filtering and pagination"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            filter_dict = filter_dict or {}
            cursor = self.db[collection_name].find(filter_dict)
            
            if sort_field:
                cursor = cursor.sort(sort_field, sort_order)
            
            cursor = cursor.skip(skip).limit(limit)
            
            documents = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                documents.append(doc)
            
            return documents
        except Exception as e:
            raise Exception(f"Failed to get documents: {e}")
    
    async def update_document(
        self, 
        collection_name: str, 
        document_id: str, 
        update_data: Dict[str, Any]
    ) -> bool:
        """Update a document by ID"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            from bson import ObjectId
            
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            if not update_data:
                return True
            
            if ObjectId.is_valid(document_id):
                result = await self.db[collection_name].update_one(
                    {"_id": ObjectId(document_id)},
                    {"$set": update_data}
                )
            else:
                id_field = self.id_fields.get(collection_name, f"{collection_name[:-1].lower()}_id")
                result = await self.db[collection_name].update_one(
                    {id_field: document_id},
                    {"$set": update_data}
                )
            
            return result.modified_count > 0
        except Exception as e:
            raise Exception(f"Failed to update document: {e}")
    
    async def delete_document(self, collection_name: str, document_id: str) -> bool:
        """Delete a document by ID"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            from bson import ObjectId
            
            if ObjectId.is_valid(document_id):
                result = await self.db[collection_name].delete_one({"_id": ObjectId(document_id)})
            else:
                id_field = self.id_fields.get(collection_name, f"{collection_name[:-1].lower()}_id")
                result = await self.db[collection_name].delete_one({id_field: document_id})
            
            return result.deleted_count > 0
        except Exception as e:
            raise Exception(f"Failed to delete document: {e}")
    
    async def count_documents(self, collection_name: str, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Count documents in a collection"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            filter_dict = filter_dict or {}
            return await self.db[collection_name].count_documents(filter_dict)
        except Exception as e:
            raise Exception(f"Failed to count documents: {e}")
    
    # Collection-specific operations
    async def get_amenities_by_units(self, unit_ids: List[str]) -> List[Dict[str, Any]]:
        """Get amenities available for specific units"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            cursor = self.db["Amenities"].find({
                "assigned_units": {"$in": unit_ids}
            })
            amenities = []
            async for amenity in cursor:
                amenity["_id"] = str(amenity["_id"])
                amenities.append(amenity)
            return amenities
        except Exception as e:
            raise Exception(f"Failed to get amenities by units: {e}")
    
    async def get_tenant_by_unit(self, unit_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant information by unit ID"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            tenant = await self.db["Tenants"].find_one({"unit_id": unit_id})
            if tenant:
                tenant["_id"] = str(tenant["_id"])
            return tenant
        except Exception as e:
            raise Exception(f"Failed to get tenant by unit: {e}")
    
    async def get_unit_by_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get unit information by tenant ID"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            unit = await self.db["Units"].find_one({"tenant_id": tenant_id})
            if unit:
                unit["_id"] = str(unit["_id"])
            return unit
        except Exception as e:
            raise Exception(f"Failed to get unit by tenant: {e}")
    
    async def get_bills_by_unit(self, unit_id: str, bill_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get bills for a specific unit"""
        try:
            filter_dict = {"unit_id": unit_id}
            if bill_type:
                collection_name = f"{bill_type.capitalize()}Bill"
            else:
                # Get from both collections
                electric_bills = await self.get_documents("ElecBill", filter_dict)
                water_bills = await self.get_documents("WaterBill", filter_dict)
                return electric_bills + water_bills
            
            return await self.get_documents(collection_name, filter_dict)
        except Exception as e:
            raise Exception(f"Failed to get bills by unit: {e}")
    
    async def get_maintenance_by_unit(self, unit_id: str) -> List[Dict[str, Any]]:
        """Get maintenance requests for a specific unit"""
        try:
            return await self.get_documents("Maintenance", {"unit_id": unit_id})
        except Exception as e:
            raise Exception(f"Failed to get maintenance by unit: {e}")
    
    async def get_contract_by_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get contract information by tenant ID"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            contract = await self.db["Contracts"].find_one({"tenant_id": tenant_id})
            if contract:
                contract["_id"] = str(contract["_id"])
            return contract
        except Exception as e:
            raise Exception(f"Failed to get contract by tenant: {e}")
    
    async def get_rent_by_unit_and_month(self, unit_id: str, month: str) -> Optional[Dict[str, Any]]:
        """Get rent information for a specific unit and month"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            rent = await self.db["Rent"].find_one({"unit_id": unit_id, "month": month})
            if rent:
                rent["_id"] = str(rent["_id"])
            return rent
        except Exception as e:
            raise Exception(f"Failed to get rent by unit and month: {e}")
    
    # Aggregation operations for summaries
    async def get_bills_summary(self, period: Optional[str] = None) -> Dict[str, Any]:
        """Get summary of bills for a specific period"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            match_stage = {}
            if period:
                match_stage["due_date"] = {"$regex": f"^{period}"}
            
            # Electric bills aggregation
            elec_pipeline = [
                {"$match": match_stage},
                {"$group": {
                    "_id": None,
                    "total_amount": {"$sum": "$amount"},
                    "paid_count": {"$sum": {"$cond": [{"$eq": ["$status", "paid"]}, 1, 0]}},
                    "unpaid_count": {"$sum": {"$cond": [{"$eq": ["$status", "unpaid"]}, 1, 0]}},
                    "due_count": {"$sum": {"$cond": [{"$eq": ["$status", "due"]}, 1, 0]}}
                }}
            ]
            
            elec_result: List[Dict[str, Any]] = await self.db["ElecBill"].aggregate(elec_pipeline).to_list(1)
            logger.info(f"Electric bills aggregation for period={period or 'all'}: {len(elec_result)} results")
            
            # Water bills aggregation
            water_pipeline = [
                {"$match": match_stage},
                {"$group": {
                    "_id": None,
                    "total_amount": {"$sum": "$amount"},
                    "paid_count": {"$sum": {"$cond": [{"$eq": ["$status", "paid"]}, 1, 0]}},
                    "unpaid_count": {"$sum": {"$cond": [{"$eq": ["$status", "unpaid"]}, 1, 0]}},
                    "due_count": {"$sum": {"$cond": [{"$eq": ["$status", "due"]}, 1, 0]}}
                }}
            ]
            
            water_result: List[Dict[str, Any]] = await self.db["WaterBill"].aggregate(water_pipeline).to_list(1)
            logger.info(f"Water bills aggregation for period={period or 'all'}: {len(water_result)} results")
            
            # Combine results
            total_amount = 0
            total_paid = 0
            total_unpaid = 0
            total_due = 0
            
            if elec_result:
                total_amount += elec_result[0]["total_amount"]
                total_paid += elec_result[0]["paid_count"]
                total_unpaid += elec_result[0]["unpaid_count"]
                total_due += elec_result[0]["due_count"]
            
            if water_result:
                total_amount += water_result[0]["total_amount"]
                total_paid += water_result[0]["paid_count"]
                total_unpaid += water_result[0]["unpaid_count"]
                total_due += water_result[0]["due_count"]
            
            result = {
                "period": period or "all",
                "total_amount": total_amount,
                "paid_items": total_paid,
                "unpaid_items": total_unpaid,
                "due_items": total_due
            }
            logger.info(f"Bills summary for period={period or 'all'}: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to get bills summary for period={period or 'all'}: {e}")
            raise Exception(f"Failed to get bills summary: {e}")
    
    async def get_property_summary(self) -> Dict[str, Any]:
        """Get overall property summary"""
        try:
            if self.db is None:
                raise Exception("Database not initialized. Call connect() first.")
            
            # Count units
            total_units = await self.count_documents("Units")
            occupied_units = await self.count_documents("Units", {"status": "occupied"})
            vacant_units = total_units - occupied_units
            
            # Count tenants and staff
            total_tenants = await self.count_documents("Tenants")
            total_staff = await self.count_documents("Staff")
            
            # Count pending maintenance
            pending_maintenance = await self.count_documents("Maintenance", {"status": "pending"})
            
            # Calculate monthly income (from active contracts)
            income_pipeline = [
                {"$match": {"status": "active"}},
                {"$group": {"_id": None, "total_income": {"$sum": "$monthly_rent"}}}
            ]
            income_result = await self.db["Contracts"].aggregate(income_pipeline).to_list(1)
            monthly_income = income_result[0].get("total_income", 0) if income_result else 0
            
            # Calculate monthly expenses (from current month expenses)
            expense_pipeline = [
                {"$match": {"date": {"$regex": f"^{datetime.now().strftime('%Y-%m')}"}}},
                {"$group": {"_id": None, "total_expenses": {"$sum": "$amount"}}}
            ]
            expense_result = await self.db["Expenses"].aggregate(expense_pipeline).to_list(1)
            monthly_expenses = expense_result[0].get("total_expenses", 0) if expense_result else 0
            
            return {
                "total_units": total_units,
                "occupied_units": occupied_units,
                "vacant_units": vacant_units,
                "total_tenants": total_tenants,
                "total_staff": total_staff,
                "pending_maintenance": pending_maintenance,
                "monthly_income": monthly_income,
                "monthly_expenses": monthly_expenses
            }
        except Exception as e:
            raise Exception(f"Failed to get property summary: {e}")
    
    # Search operations for RAG
    async def search_documents(
        self, 
        collection_name: str, 
        search_term: str, 
        search_fields: List[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search documents using text search across specified fields"""
        try:
            # Create regex search for each field
            or_conditions = []
            for field in search_fields:
                or_conditions.append({field: {"$regex": search_term, "$options": "i"}})
            
            filter_dict = {"$or": or_conditions}
            return await self.get_documents(collection_name, filter_dict, limit=limit)
        except Exception as e:
            raise Exception(f"Failed to search documents: {e}")

# Global database instance
db_manager = DatabaseManager()

async def get_database():
    """Dependency to get database manager"""
    if not db_manager.client:
        await db_manager.connect()
    return db_manager
