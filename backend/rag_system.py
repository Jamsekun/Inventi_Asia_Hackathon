#Mock rag system
import re
import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import asyncio
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from .database import DatabaseManager
from .models import ChatRequest, RAGResponse

logger = logging.getLogger(__name__)

class RAGSystem:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.model = None
        self.intent_patterns = self._load_intent_patterns()
        self.collection_schemas = self._load_collection_schemas()
        
    async def initialize(self):
        """Initialize the RAG system with sentence transformer model"""
        try:
            # Use a lightweight model for embeddings
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("RAG system initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RAG system: {e}")
            # Fallback to simple text matching
            self.model = None
    
    def _load_intent_patterns(self) -> Dict[str, List[str]]:
        """Load intent detection patterns based on the schema document"""
        return {
            "AMENITIES_INFO": [
                r"pool|swimming|gym|amenity|facility|available|reserve|function hall",
                r"pwede.*gamit|can.*use|which.*units|available.*pool"
            ],
            "CONTRACT_STATUS": [
                r"contract|lease|expire|monthly.*rent|deposit|status.*contract",
                r"mag.*expire|lease.*ni|contract.*sa|monthly.*rent|deposit.*refund"
            ],
            "BILLING_INFO": [
                r"bill|soa|electric|water|kuryente|tubig|latest.*soa|elecbill|waterbill",
                r"magkano.*soa|latest.*bill|electric.*bill|water.*bill"
            ],
            "EXPENSES_INFO": [
                r"expense|gastos|spent|cost|maintenance.*cost|elevator.*repair",
                r"magkano.*nagastos|total.*expenses|gastos.*sa"
            ],
            "MAINTENANCE_REQUEST": [
                r"maintenance|repair|issue|aircon|plumbing|elevator|leak|fix",
                r"naayos|status.*maintenance|resolved|reported.*date|water.*leak"
            ],
            "RENT_INFO": [
                r"rent|renta|payment|nabayaran|monthly.*rent|rent.*soa",
                r"magkano.*renta|rent.*ng|payment.*date|unpaid.*rent"
            ],
            "STAFF_INFO": [
                r"staff|plumber|security|janitor|assigned|contact.*number|naka.*assign",
                r"sino.*assign|contact.*number|security.*guard|maintenance.*handle"
            ],
            "TENANT_QUERY": [
                r"tenant|contact.*number|email.*address|who.*tenant|renting",
                r"contact.*number.*ni|email.*address.*ng|tenant.*sa"
            ],
            "UNIT_INFO": [
                r"unit|occupied|vacant|floor|status.*unit|rented.*or.*vacant",
                r"occupied.*pa.*ba|which.*floor|status.*ng|tenant.*naka.*assign"
            ]
        }
    
    def _load_collection_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Load collection schemas for context"""
        return {
            "Amenities": {
                "fields": ["amenity_id", "name", "description", "availability", "assigned_units"],
                "searchable": ["name", "description"]
            },
            "Contracts": {
                "fields": ["contract_id", "tenant_id", "unit_id", "monthly_rent", "deposit", "start_date", "end_date", "status"],
                "searchable": ["tenant_id", "unit_id", "status"]
            },
            "ElecBill": {
                "fields": ["bill_id", "unit_id", "amount", "due_date", "status"],
                "searchable": ["unit_id", "status"]
            },
            "WaterBill": {
                "fields": ["bill_id", "unit_id", "amount", "due_date", "status"],
                "searchable": ["unit_id", "status"]
            },
            "Expenses": {
                "fields": ["expense_id", "category", "amount", "date", "description"],
                "searchable": ["category", "description"]
            },
            "Maintenance": {
                "fields": ["request_id", "unit_id", "issue", "status", "reported_date", "resolved_date"],
                "searchable": ["unit_id", "issue", "status"]
            },
            "Rent": {
                "fields": ["rent_id", "unit_id", "tenant_id", "amount", "month", "status", "payment_date"],
                "searchable": ["unit_id", "tenant_id", "month", "status"]
            },
            "Staff": {
                "fields": ["staff_id", "name", "role", "contact", "assigned_requests"],
                "searchable": ["name", "role"]
            },
            "Tenants": {
                "fields": ["tenant_id", "name", "contact", "email", "unit_id"],
                "searchable": ["name", "contact", "email", "unit_id"]
            },
            "Units": {
                "fields": ["unit_id", "floor", "number", "status", "tenant_id"],
                "searchable": ["unit_id", "number", "status", "tenant_id"]
            }
        }
    
    def detect_intent(self, user_query: str) -> Tuple[str, float]:
        """Detect user intent from query using pattern matching and embeddings"""
        user_query_lower = user_query.lower()
        
        # Pattern-based intent detection
        intent_scores = {}
        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, user_query_lower, re.IGNORECASE):
                    score += 1
            intent_scores[intent] = score
        
        # Find best matching intent
        if intent_scores:
            best_intent = max(intent_scores.keys(), key=lambda k: intent_scores[k])
            confidence = intent_scores[best_intent] / len(self.intent_patterns[best_intent])
            return best_intent, confidence
        
        # Fallback to embedding-based similarity if model is available
        if self.model:
            return self._detect_intent_with_embeddings(user_query)
        
        return "GENERAL_QUERY", 0.0
    
    def _detect_intent_with_embeddings(self, user_query: str) -> Tuple[str, float]:
        """Detect intent using sentence embeddings"""
        try:
            # Check if model is initialized
            if self.model is None:
                logger.warning("Sentence transformer model not initialized, falling back to pattern matching")
                return "GENERAL_QUERY", 0.0
            
            # Create example queries for each intent
            intent_examples = {
                "AMENITIES_INFO": "Is the swimming pool available for unit U-101?",
                "CONTRACT_STATUS": "When does the lease expire for tenant T-001?",
                "BILLING_INFO": "What is the latest electricity bill for unit U-101?",
                "EXPENSES_INFO": "How much was spent on elevator repair last month?",
                "MAINTENANCE_REQUEST": "Is the aircon issue in unit U-101 resolved?",
                "RENT_INFO": "Has the September rent for unit U-101 been paid?",
                "STAFF_INFO": "Who is the plumber assigned to handle maintenance?",
                "TENANT_QUERY": "What is the contact number for the tenant in unit U-101?",
                "UNIT_INFO": "Is unit U-101 currently occupied or vacant?"
            }
            
            # Get embeddings
            query_embedding = self.model.encode([user_query])
            example_embeddings = self.model.encode(list(intent_examples.values()))
            
            # Calculate similarities
            similarities = cosine_similarity(query_embedding, example_embeddings)[0]
            
            # Find best match
            best_idx = np.argmax(similarities)
            best_intent = list(intent_examples.keys())[best_idx]
            confidence = similarities[best_idx]
            
            return best_intent, float(confidence)
        except Exception as e:
            logger.error(f"Error in embedding-based intent detection: {e}")
            return "GENERAL_QUERY", 0.0
    
    def _extract_entities(self, query: str) -> Dict[str, Any]:
        """Extract entities like unit IDs, tenant IDs, or status from query"""
        entities = {}
        query_lower = query.lower()
        
        # Extract unit_id (e.g., U-101)
        unit_match = re.search(r'\bU-\d+\b', query, re.IGNORECASE)
        if unit_match:
            entities["unit_id"] = unit_match.group(0)
        
        # Extract tenant_id (e.g., T-001)
        tenant_match = re.search(r'\bT-\d+\b', query, re.IGNORECASE)
        if tenant_match:
            entities["tenant_id"] = tenant_match.group(0)
        
        # Extract status (e.g., paid, unpaid, due, pending, resolved)
        status_match = re.search(r'\b(paid|unpaid|due|pending|resolved)\b', query_lower)
        if status_match:
            entities["status"] = status_match.group(0)
        
        # Extract period (e.g., 2025-09)
        period_match = re.search(r'\b(\d{4}-\d{2})\b', query)
        if period_match:
            entities["period"] = period_match.group(0)
        
        # Extract role keywords for staff (e.g., plumber, electrician)
        role_keywords = re.findall(r'\b(plumber|electrician|security|janitor|maintenance|guard)\b', query_lower)
        if role_keywords:
            entities["role_keywords"] = role_keywords
        
        logger.info(f"Extracted entities from query '{query}': {entities}")
        return entities
    
    async def retrieve_relevant_data(self, intent: str, query: str) -> Dict[str, Any]:
        """Retrieve relevant data based on detected intent and query"""
        try:
            relevant_data = {}
            entities = self._extract_entities(query)
            
            if intent == "AMENITIES_INFO":
                relevant_data = await self._retrieve_amenities_data(entities)
            elif intent == "CONTRACT_STATUS":
                relevant_data = await self._retrieve_contracts_data(entities)
            elif intent == "BILLING_INFO":
                relevant_data = await self._retrieve_bills_data(entities)
            elif intent == "EXPENSES_INFO":
                relevant_data = await self._retrieve_expenses_data(entities)
            elif intent == "MAINTENANCE_REQUEST":
                relevant_data = await self._retrieve_maintenance_data(entities)
            elif intent == "RENT_INFO":
                relevant_data = await self._retrieve_rent_data(entities)
            elif intent == "STAFF_INFO":
                relevant_data = await self._retrieve_staff_data(entities)
            elif intent == "TENANT_QUERY":
                relevant_data = await self._retrieve_tenants_data(entities)
            elif intent == "UNIT_INFO":
                relevant_data = await self._retrieve_units_data(entities)
            else:
                relevant_data = await self._retrieve_general_data(query)
            
            logger.info(f"Retrieved data for intent '{intent}': {relevant_data}")
            return relevant_data
        except Exception as e:
            logger.error(f"Error retrieving data for intent '{intent}': {e}")
            return {}
    
    async def _retrieve_amenities_data(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve amenities data based on entities"""
        unit_id = entities.get("unit_id")
        if unit_id:
            return {
                "amenities": await self.db_manager.get_amenities_by_units([unit_id])
            }
        else:
            filter_dict = {}
            return {
                "amenities": await self.db_manager.get_documents("Amenities", filter_dict)
            }

    
    async def _retrieve_contracts_data(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve contracts data based on entities"""
        filter_dict = {}
        if "tenant_id" in entities:
            filter_dict["tenant_id"] = entities["tenant_id"]
        if "unit_id" in entities:
            filter_dict["unit_id"] = entities["unit_id"]
        if "status" in entities:
            filter_dict["status"] = entities["status"]
        return {"contracts": await self.db_manager.get_documents("Contracts", filter_dict)}
    
    async def _retrieve_bills_data(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve bills data based on entities"""
        filter_dict = {}
        if "unit_id" in entities:
            filter_dict["unit_id"] = entities["unit_id"]
        if "status" in entities:
            filter_dict["status"] = entities["status"]
        if "period" in entities:
            filter_dict["due_date"] = {"$regex": f"^{entities['period']}"}
        
        elec_bills = await self.db_manager.get_documents("ElecBill", filter_dict)
        water_bills = await self.db_manager.get_documents("WaterBill", filter_dict)
        logger.info(f"Retrieved {len(elec_bills)} electric bills and {len(water_bills)} water bills for entities: {entities}")
        return {"bills": elec_bills + water_bills}
    
    async def _retrieve_expenses_data(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve expenses data based on entities"""
        filter_dict = {}
        if "period" in entities:
            filter_dict["date"] = {"$regex": f"^{entities['period']}"}
        return {"expenses": await self.db_manager.get_documents("Expenses", filter_dict)}
    
    async def _retrieve_maintenance_data(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve maintenance data based on entities"""
        filter_dict = {}
        if "unit_id" in entities:
            filter_dict["unit_id"] = entities["unit_id"]
        if "status" in entities:
            filter_dict["status"] = entities["status"]
        return {"maintenance": await self.db_manager.get_documents("Maintenance", filter_dict)}
    
    async def _retrieve_rent_data(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve rent data based on entities"""
        filter_dict = {}
        if "unit_id" in entities:
            filter_dict["unit_id"] = entities["unit_id"]
        if "tenant_id" in entities:
            filter_dict["tenant_id"] = entities["tenant_id"]
        if "status" in entities:
            filter_dict["status"] = entities["status"]
        if "period" in entities:
            filter_dict["month"] = entities["period"]
        return {"rent": await self.db_manager.get_documents("Rent", filter_dict)}
    
    async def _retrieve_staff_data(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve staff data based on entities"""
        filter_dict = {}
        if "role_keywords" in entities:
            # Use $or for multiple keywords
            or_conditions = [{"role": {"$regex": keyword, "$options": "i"}} for keyword in entities["role_keywords"]]
            filter_dict["$or"] = or_conditions
        return {"staff": await self.db_manager.get_documents("Staff", filter_dict)}
    
    async def _retrieve_tenants_data(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve tenants data based on entities"""
        filter_dict = {}
        if "unit_id" in entities:
            filter_dict["unit_id"] = entities["unit_id"]
        if "tenant_id" in entities:
            filter_dict["tenant_id"] = entities["tenant_id"]
        return {"tenants": await self.db_manager.get_documents("Tenants", filter_dict)}
    
    async def _retrieve_units_data(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve units data based on entities"""
        filter_dict = {}
        if "unit_id" in entities:
            filter_dict["unit_id"] = entities["unit_id"]
        if "status" in entities:
            filter_dict["status"] = entities["status"]
        return {"units": await self.db_manager.get_documents("Units", filter_dict)}
    
    async def _retrieve_general_data(self, query: str) -> Dict[str, Any]:
        """Retrieve general data for unknown intent"""
        relevant_data = {}
        for collection, schema in self.collection_schemas.items():
            results = await self.db_manager.search_documents(collection, query, schema["searchable"])
            if results:
                relevant_data[collection.lower()] = results  # Use lower for consistency in data keys
        return relevant_data
    
    def generate_response(self, intent: str, relevant_data: Dict[str, Any], original_query: str) -> str:
        """Generate a response based on intent and retrieved data"""
        try:
            greeting = "Sure, let me check that for you!"
            if intent == "AMENITIES_INFO":
                return f"{greeting} {self._generate_amenities_response(relevant_data, original_query)} Let me know if you'd like more details about availability or reservations!"
            elif intent == "CONTRACT_STATUS":
                return f"{greeting} {self._generate_contracts_response(relevant_data, original_query)} If you need more info like renewal options or deposit details, just ask!"
            elif intent == "BILLING_INFO":
                return f"{greeting} {self._generate_bills_response(relevant_data, original_query)} Feel free to ask about specific bills or payment options if needed!"
            elif intent == "EXPENSES_INFO":
                return f"{greeting} {self._generate_expenses_response(relevant_data, original_query)} Let me know if you'd like breakdowns by category or dates!"
            elif intent == "MAINTENANCE_REQUEST":
                return f"{greeting} {self._generate_maintenance_response(relevant_data, original_query)} If you want updates on specific issues or to report a new one, I'm here to help!"
            elif intent == "RENT_INFO":
                return f"{greeting} {self._generate_rent_response(relevant_data, original_query)} If you'd like details on payments or due dates, just let me know!"
            elif intent == "STAFF_INFO":
                return f"{greeting} {self._generate_staff_response(relevant_data, original_query)} Let me know if you want more about other staff, their contact numbers, or assignments!"
            elif intent == "TENANT_QUERY":
                return f"{greeting} {self._generate_tenants_response(relevant_data, original_query)} If you need more details like contact info or lease terms, feel free to ask!"
            elif intent == "UNIT_INFO":
                return f"{greeting} {self._generate_units_response(relevant_data, original_query)} Let me know if you'd like info on availability, tenants, or maintenance for specific units!"
            else:
                return f"{greeting} {self._generate_general_response(relevant_data, original_query)} If this isn't what you meant, could you clarify?"
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I apologize, but I encountered an error while processing your request. Please try again, or let me know how I can assist better!"
    
    def _generate_amenities_response(self, data: Dict[str, Any], query: str) -> str:
        """Generate response for amenities queries"""
        amenities: List[Dict[str, Any]] = data.get("amenities", [])
        
        if not amenities:
            return "I couldn't find any amenities matching your query."
        
        if len(amenities) == 1:
            amenity: Dict[str, Any] = amenities[0]
            status = "available" if amenity.get("availability", False) else "not available"
            units = ", ".join(amenity.get("assigned_units", [])) or "all units"
            return f"The {amenity.get('name', 'amenity')} is {status}. It's accessible to {units}."
        
        response = "Here's what I found on amenities:\n"
        for amenity in amenities[:5]:
            status = "available" if amenity.get("availability", False) else "not available"
            response += f"- {amenity.get('name', 'Unknown')}: {status}\n"
        
        return response
    
    def _generate_contracts_response(self, data: Dict[str, Any], query: str) -> str:
        """Generate response for contracts queries"""
        contracts: List[Dict[str, Any]] = data.get("contracts", [])
        
        if not contracts:
            return "I couldn't find any contract information."
        
        if len(contracts) == 1:
            contract: Dict[str, Any] = contracts[0]
            return f"For contract {contract.get('contract_id', 'Unknown')} in unit {contract.get('unit_id', 'Unknown')}: The monthly rent is ₱{contract.get('monthly_rent', 0):,.2f}, status is {contract.get('status', 'Unknown')}, and it expires on {contract.get('end_date', 'Unknown')}."
        
        response = "Here's a summary of the contracts I found:\n"
        for contract in contracts[:5]:
            response += f"- Contract {contract.get('contract_id', 'Unknown')}: Unit {contract.get('unit_id', 'Unknown')}, Status: {contract.get('status', 'Unknown')}\n"
        
        return response
    
    def _generate_bills_response(self, data: Dict[str, Any], query: str) -> str:
        """Generate response for bills queries"""
        bills: List[Dict[str, Any]] = data.get("bills", [])
        
        if not bills:
            return "I couldn't find any bill information."
        
        total_amount = sum(bill.get("amount", 0) for bill in bills)
        paid_count = sum(1 for bill in bills if bill.get("status") == "paid")
        unpaid_count = len(bills) - paid_count
        
        return f"I found {len(bills)} bills totaling ₱{total_amount:,.2f}. Of these, {paid_count} are paid and {unpaid_count} are unpaid."
    
    def _generate_expenses_response(self, data: Dict[str, Any], query: str) -> str:
        """Generate response for expenses queries"""
        expenses: List[Dict[str, Any]] = data.get("expenses", [])
        
        if not expenses:
            return "I couldn't find any expense information."
        
        total_amount = sum(expense.get("amount", 0) for expense in expenses)
        
        return f"There are {len(expenses)} expenses recorded, adding up to ₱{total_amount:,.2f}."
    
    def _generate_maintenance_response(self, data: Dict[str, Any], query: str) -> str:
        """Generate response for maintenance queries"""
        maintenance: List[Dict[str, Any]] = data.get("maintenance", [])
        
        if not maintenance:
            return "I couldn't find any maintenance requests."
        
        pending_count = sum(1 for req in maintenance if req.get("status") == "pending")
        resolved_count = len(maintenance) - pending_count
        
        return f"There are {len(maintenance)} maintenance requests in total. {pending_count} are still pending, and {resolved_count} have been resolved."
    
    def _generate_rent_response(self, data: Dict[str, Any], query: str) -> str:
        """Generate response for rent queries"""
        rent_records: List[Dict[str, Any]] = data.get("rent", [])
        
        if not rent_records:
            return "I couldn't find any rent information."
        
        total_amount = sum(record.get("amount", 0) for record in rent_records)
        paid_count = sum(1 for record in rent_records if record.get("status") == "paid")
        unpaid_count = len(rent_records) - paid_count
        
        return f"I found {len(rent_records)} rent records totaling ₱{total_amount:,.2f}. {paid_count} are paid, and {unpaid_count} are unpaid."
    
    def _generate_staff_response(self, data: Dict[str, Any], query: str) -> str:
        """Generate response for staff queries"""
        staff: List[Dict[str, Any]] = data.get("staff", [])
        
        if not staff:
            return "I couldn't find any staff information."
        
        # Improved filtering: extract keywords from query
        query_lower = query.lower()
        keywords = re.findall(r'\b(plumber|electrician|security|janitor|maintenance|guard|assigned)\b', query_lower)
        if not keywords:
            keywords = query_lower.split()  # Fallback to split words
        
        filtered_staff = []
        for member in staff:
            role_lower = member.get("role", "").lower()
            name_lower = member.get("name", "").lower()
            if any(keyword in role_lower or keyword in name_lower for keyword in keywords):
                filtered_staff.append(member)
        
        if not filtered_staff:
            return "I couldn't find any matching staff for your query."
        
        if len(filtered_staff) == 1:
            member: Dict[str, Any] = filtered_staff[0]
            return f"The assigned {member.get('role', 'staff member')} is {member.get('name', 'Unknown')}. Their contact is {member.get('contact', 'Unknown')}."
        
        response = "Here are the matching staff members:\n"
        for member in filtered_staff[:5]:  # Limit to 5
            response += f"- {member.get('name', 'Unknown')}: {member.get('role', 'Unknown')}, Contact: {member.get('contact', 'Unknown')}\n"
        
        return response
    
    def _generate_tenants_response(self, data: Dict[str, Any], query: str) -> str:
        """Generate response for tenant queries"""
        tenants: List[Dict[str, Any]] = data.get("tenants", [])
        
        if not tenants:
            return "I couldn't find any tenant information."
        
        if len(tenants) == 1:
            tenant: Dict[str, Any] = tenants[0]
            return f"The tenant is {tenant.get('tenant_id', 'Unknown')}, with status {tenant.get('status', 'Unknown')}, in unit {tenant.get('unit_id', 'Unknown')}."
        
        response = "Here are the tenants I found:\n"
        for tenant in tenants[:5]:
            response += f"- {tenant.get('name', 'Unknown')}: Unit {tenant.get('unit_id', 'Unknown')}, Contact: {tenant.get('contact', 'Unknown')}\n"
        
        return response
    
    def _generate_units_response(self, data: Dict[str, Any], query: str) -> str:
        """Generate response for unit queries"""
        units: List[Dict[str, Any]] = data.get("units", [])
        
        if not units:
            return "I couldn't find any unit information."
        
        if len(units) == 1:
            unit: Dict[str, Any] = units[0]
            return f"Unit {unit.get('unit_id', 'Unknown')} on floor {unit.get('floor', 'Unknown')} is {unit.get('status', 'Unknown')}, with tenant {unit.get('tenant_id', 'None')}."
        
        occupied_count = sum(1 for unit in units if unit.get("status") == "occupied")
        vacant_count = len(units) - occupied_count
        
        return f"I found {len(units)} units in total. {occupied_count} are occupied, and {vacant_count} are vacant."
    
    def _generate_general_response(self, data: Dict[str, Any], query: str) -> str:
        """Generate response for general queries"""
        if not data:
            return "I couldn't find any relevant information for your query. Could you provide more details?"
        
        response = "Here's what I found related to your query:\n"
        for collection, items in data.items():
            if items:
                response += f"- In {collection}: {len(items)} records found\n"
        
        return response
    
    async def process_query(self, chat_request: ChatRequest) -> RAGResponse:
        """Process a chat query and return RAG response"""
        try:
            # Get the latest user message
            user_messages = [msg for msg in chat_request.messages if msg.role == "user"]
            if not user_messages:
                return RAGResponse(
                    intent="ERROR",
                    response="No user message found in the request.",
                    relevant_data={}
                )
            
            latest_query = user_messages[-1].content
            
            # Detect intent
            intent, confidence = self.detect_intent(latest_query)
            
            # Retrieve relevant data
            relevant_data = await self.retrieve_relevant_data(intent, latest_query)
            
            # Generate response
            response = self.generate_response(intent, relevant_data, latest_query)
            
            return RAGResponse(
                intent=intent,
                response=response,
                relevant_data=relevant_data
            )
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return RAGResponse(
                intent="ERROR",
                response="I apologize, but I encountered an error while processing your request. Please try again.",
                relevant_data={}
            )