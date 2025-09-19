#!/usr/bin/env python3
## testing only might delete later
"""
Seed script to populate MongoDB with sample property management data
Based on the schema from InfinityCondo_DatasetGen_PROMPT.md
"""

import asyncio
import os
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "MockPropDB")

class MockDataSeeder:
    def __init__(self):
        self.client = None
        self.db = None
        
    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(MONGODB_URI)
            self.db = self.client[MONGODB_DB]
            await self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {MONGODB_URI}/{MONGODB_DB}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def clear_database(self):
        """Clear all existing data"""
        collections = ["amenities", "contracts", "elecbills", "waterbills", "expenses", 
                      "maintenance", "rent", "staff", "tenants", "units"]
        
        for collection_name in collections:
            await self.db[collection_name].delete_many({})
            logger.info(f"Cleared collection: {collection_name}")
    
    async def seed_amenities(self):
        """Seed amenities data"""
        amenities = [
            {
                "amenity_id": "A-001",
                "name": "Swimming Pool",
                "description": "Outdoor pool available for all tenants",
                "availability": True,
                "assigned_units": ["U-101", "U-102", "U-201", "U-202", "U-301", "U-302", "U-401", "U-402", "U-501", "U-502"]
            },
            {
                "amenity_id": "A-002",
                "name": "Gym",
                "description": "Fully equipped fitness center",
                "availability": True,
                "assigned_units": ["U-101", "U-102", "U-201", "U-202", "U-301", "U-302", "U-401", "U-402", "U-501", "U-502"]
            },
            {
                "amenity_id": "A-003",
                "name": "Function Hall",
                "description": "Event space for gatherings and celebrations",
                "availability": True,
                "assigned_units": ["U-101", "U-102", "U-201", "U-202", "U-301", "U-302", "U-401", "U-402", "U-501", "U-502"]
            },
            {
                "amenity_id": "A-004",
                "name": "Parking Area",
                "description": "Designated parking spaces for tenants",
                "availability": True,
                "assigned_units": ["U-101", "U-102", "U-201", "U-202", "U-301", "U-302", "U-401", "U-402", "U-501", "U-502"]
            }
        ]
        
        await self.db.amenities.insert_many(amenities)
        logger.info(f"Seeded {len(amenities)} amenities")
    
    async def seed_tenants(self):
        """Seed tenants data"""
        tenants = [
            {
                "tenant_id": "T-001",
                "name": "Juan dela Cruz",
                "contact": "+63-912-345-6789",
                "email": "juan.delacruz@email.com",
                "unit_id": "U-101"
            },
            {
                "tenant_id": "T-002",
                "name": "Maria Santos",
                "contact": "+63-917-234-5678",
                "email": "maria.santos@email.com",
                "unit_id": "U-102"
            },
            {
                "tenant_id": "T-003",
                "name": "Pedro Rodriguez",
                "contact": "+63-918-345-6789",
                "email": "pedro.rodriguez@email.com",
                "unit_id": "U-201"
            },
            {
                "tenant_id": "T-004",
                "name": "Ana Garcia",
                "contact": "+63-919-456-7890",
                "email": "ana.garcia@email.com",
                "unit_id": "U-202"
            },
            {
                "tenant_id": "T-005",
                "name": "Carlos Lopez",
                "contact": "+63-920-567-8901",
                "email": "carlos.lopez@email.com",
                "unit_id": "U-301"
            }
        ]
        
        await self.db.tenants.insert_many(tenants)
        logger.info(f"Seeded {len(tenants)} tenants")
    
    async def seed_units(self):
        """Seed units data"""
        units = [
            {"unit_id": "U-101", "floor": 1, "number": "101", "status": "occupied", "tenant_id": "T-001"},
            {"unit_id": "U-102", "floor": 1, "number": "102", "status": "occupied", "tenant_id": "T-002"},
            {"unit_id": "U-201", "floor": 2, "number": "201", "status": "occupied", "tenant_id": "T-003"},
            {"unit_id": "U-202", "floor": 2, "number": "202", "status": "occupied", "tenant_id": "T-004"},
            {"unit_id": "U-301", "floor": 3, "number": "301", "status": "occupied", "tenant_id": "T-005"},
            {"unit_id": "U-302", "floor": 3, "number": "302", "status": "vacant", "tenant_id": None},
            {"unit_id": "U-401", "floor": 4, "number": "401", "status": "vacant", "tenant_id": None},
            {"unit_id": "U-402", "floor": 4, "number": "402", "status": "vacant", "tenant_id": None},
            {"unit_id": "U-501", "floor": 5, "number": "501", "status": "vacant", "tenant_id": None},
            {"unit_id": "U-502", "floor": 5, "number": "502", "status": "vacant", "tenant_id": None}
        ]
        
        await self.db.units.insert_many(units)
        logger.info(f"Seeded {len(units)} units")
    
    async def seed_contracts(self):
        """Seed contracts data"""
        contracts = [
            {
                "contract_id": "L-101-2025",
                "tenant_id": "T-001",
                "unit_id": "U-101",
                "monthly_rent": 25000,
                "deposit": 50000,
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "status": "active"
            },
            {
                "contract_id": "L-102-2025",
                "tenant_id": "T-002",
                "unit_id": "U-102",
                "monthly_rent": 25000,
                "deposit": 50000,
                "start_date": "2025-02-01",
                "end_date": "2026-01-31",
                "status": "active"
            },
            {
                "contract_id": "L-201-2025",
                "tenant_id": "T-003",
                "unit_id": "U-201",
                "monthly_rent": 28000,
                "deposit": 56000,
                "start_date": "2025-03-01",
                "end_date": "2026-02-28",
                "status": "active"
            },
            {
                "contract_id": "L-202-2025",
                "tenant_id": "T-004",
                "unit_id": "U-202",
                "monthly_rent": 28000,
                "deposit": 56000,
                "start_date": "2025-04-01",
                "end_date": "2026-03-31",
                "status": "active"
            },
            {
                "contract_id": "L-301-2025",
                "tenant_id": "T-005",
                "unit_id": "U-301",
                "monthly_rent": 30000,
                "deposit": 60000,
                "start_date": "2025-05-01",
                "end_date": "2026-04-30",
                "status": "active"
            }
        ]
        
        await self.db.contracts.insert_many(contracts)
        logger.info(f"Seeded {len(contracts)} contracts")
    
    async def seed_bills(self):
        """Seed electric and water bills data"""
        # Electric bills
        elec_bills = [
            {
                "bill_id": "EB-2025-09-101",
                "unit_id": "U-101",
                "amount": 12000,
                "due_date": "2025-09-30",
                "status": "paid"
            },
            {
                "bill_id": "EB-2025-09-102",
                "unit_id": "U-102",
                "amount": 13500,
                "due_date": "2025-09-30",
                "status": "paid"
            },
            {
                "bill_id": "EB-2025-09-201",
                "unit_id": "U-201",
                "amount": 15000,
                "due_date": "2025-09-30",
                "status": "unpaid"
            },
            {
                "bill_id": "EB-2025-08-101",
                "unit_id": "U-101",
                "amount": 11500,
                "due_date": "2025-08-31",
                "status": "paid"
            },
            {
                "bill_id": "EB-2025-08-102",
                "unit_id": "U-102",
                "amount": 12800,
                "due_date": "2025-08-31",
                "status": "paid"
            }
        ]
        
        # Water bills
        water_bills = [
            {
                "bill_id": "WB-2025-09-101",
                "unit_id": "U-101",
                "amount": 2500,
                "due_date": "2025-09-30",
                "status": "paid"
            },
            {
                "bill_id": "WB-2025-09-102",
                "unit_id": "U-102",
                "amount": 2800,
                "due_date": "2025-09-30",
                "status": "paid"
            },
            {
                "bill_id": "WB-2025-09-201",
                "unit_id": "U-201",
                "amount": 3200,
                "due_date": "2025-09-30",
                "status": "unpaid"
            },
            {
                "bill_id": "WB-2025-08-101",
                "unit_id": "U-101",
                "amount": 2400,
                "due_date": "2025-08-31",
                "status": "paid"
            },
            {
                "bill_id": "WB-2025-08-102",
                "unit_id": "U-102",
                "amount": 2700,
                "due_date": "2025-08-31",
                "status": "paid"
            }
        ]
        
        await self.db.elecbills.insert_many(elec_bills)
        await self.db.waterbills.insert_many(water_bills)
        logger.info(f"Seeded {len(elec_bills)} electric bills and {len(water_bills)} water bills")
    
    async def seed_expenses(self):
        """Seed expenses data"""
        expenses = [
            {
                "expense_id": "E-2025-08-01",
                "category": "elevator repair",
                "amount": 50000,
                "date": "2025-08-12",
                "description": "Replaced main elevator motor"
            },
            {
                "expense_id": "E-2025-08-02",
                "category": "plumbing",
                "amount": 15000,
                "date": "2025-08-15",
                "description": "Fixed water leak in unit U-201"
            },
            {
                "expense_id": "E-2025-09-01",
                "category": "cleaning",
                "amount": 8000,
                "date": "2025-09-01",
                "description": "Monthly cleaning service"
            },
            {
                "expense_id": "E-2025-09-02",
                "category": "security",
                "amount": 12000,
                "date": "2025-09-05",
                "description": "Security system maintenance"
            },
            {
                "expense_id": "E-2025-09-03",
                "category": "electrical",
                "amount": 25000,
                "date": "2025-09-10",
                "description": "Electrical panel upgrade"
            }
        ]
        
        await self.db.expenses.insert_many(expenses)
        logger.info(f"Seeded {len(expenses)} expenses")
    
    async def seed_maintenance(self):
        """Seed maintenance requests data"""
        maintenance = [
            {
                "request_id": "MR-2025-09-001",
                "unit_id": "U-101",
                "issue": "Air conditioning not working",
                "status": "resolved",
                "reported_date": "2025-09-05",
                "resolved_date": "2025-09-07"
            },
            {
                "request_id": "MR-2025-09-002",
                "unit_id": "U-201",
                "issue": "Water leak in bathroom",
                "status": "pending",
                "reported_date": "2025-09-10",
                "resolved_date": None
            },
            {
                "request_id": "MR-2025-09-003",
                "unit_id": "U-102",
                "issue": "Door lock malfunction",
                "status": "resolved",
                "reported_date": "2025-09-08",
                "resolved_date": "2025-09-09"
            },
            {
                "request_id": "MR-2025-09-004",
                "unit_id": "U-301",
                "issue": "Elevator button not responding",
                "status": "pending",
                "reported_date": "2025-09-12",
                "resolved_date": None
            }
        ]
        
        await self.db.maintenance.insert_many(maintenance)
        logger.info(f"Seeded {len(maintenance)} maintenance requests")
    
    async def seed_rent(self):
        """Seed rent payment data"""
        rent_records = [
            {
                "rent_id": "R-2025-09-101",
                "unit_id": "U-101",
                "tenant_id": "T-001",
                "amount": 25000,
                "month": "2025-09",
                "status": "paid",
                "payment_date": "2025-09-05"
            },
            {
                "rent_id": "R-2025-09-102",
                "unit_id": "U-102",
                "tenant_id": "T-002",
                "amount": 25000,
                "month": "2025-09",
                "status": "paid",
                "payment_date": "2025-09-03"
            },
            {
                "rent_id": "R-2025-09-201",
                "unit_id": "U-201",
                "tenant_id": "T-003",
                "amount": 28000,
                "month": "2025-09",
                "status": "unpaid",
                "payment_date": None
            },
            {
                "rent_id": "R-2025-08-101",
                "unit_id": "U-101",
                "tenant_id": "T-001",
                "amount": 25000,
                "month": "2025-08",
                "status": "paid",
                "payment_date": "2025-08-05"
            },
            {
                "rent_id": "R-2025-08-102",
                "unit_id": "U-102",
                "tenant_id": "T-002",
                "amount": 25000,
                "month": "2025-08",
                "status": "paid",
                "payment_date": "2025-08-03"
            }
        ]
        
        await self.db.rent.insert_many(rent_records)
        logger.info(f"Seeded {len(rent_records)} rent records")
    
    async def seed_staff(self):
        """Seed staff data"""
        staff = [
            {
                "staff_id": "S-001",
                "name": "Roberto Santos",
                "role": "plumber",
                "contact": "+63-912-123-4567",
                "assigned_requests": ["MR-2025-09-002"]
            },
            {
                "staff_id": "S-002",
                "name": "Miguel Rodriguez",
                "role": "electrician",
                "contact": "+63-917-234-5678",
                "assigned_requests": ["MR-2025-09-001", "MR-2025-09-004"]
            },
            {
                "staff_id": "S-003",
                "name": "Elena Garcia",
                "role": "security guard",
                "contact": "+63-918-345-6789",
                "assigned_requests": []
            },
            {
                "staff_id": "S-004",
                "name": "Jose Martinez",
                "role": "janitor",
                "contact": "+63-919-456-7890",
                "assigned_requests": []
            },
            {
                "staff_id": "S-005",
                "name": "Carmen Lopez",
                "role": "maintenance supervisor",
                "contact": "+63-920-567-8901",
                "assigned_requests": ["MR-2025-09-003"]
            }
        ]
        
        await self.db.staff.insert_many(staff)
        logger.info(f"Seeded {len(staff)} staff members")
    
    async def seed_all(self):
        """Seed all collections"""
        try:
            await self.connect()
            await self.clear_database()
            
            logger.info("Starting database seeding...")
            
            await self.seed_amenities()
            await self.seed_tenants()
            await self.seed_units()
            await self.seed_contracts()
            await self.seed_bills()
            await self.seed_expenses()
            await self.seed_maintenance()
            await self.seed_rent()
            await self.seed_staff()
            
            logger.info("✅ Database seeding completed successfully!")
            
            # Print summary
            collections = ["amenities", "contracts", "elecbills", "waterbills", "expenses", 
                          "maintenance", "rent", "staff", "tenants", "units"]
            
            logger.info("\n📊 Database Summary:")
            for collection_name in collections:
                count = await self.db[collection_name].count_documents({})
                logger.info(f"  {collection_name}: {count} documents")
            
        except Exception as e:
            logger.error(f"❌ Error during seeding: {e}")
            raise
        finally:
            await self.disconnect()

async def main():
    """Main function to run the seeder"""
    seeder = MockDataSeeder()
    await seeder.seed_all()

if __name__ == "__main__":
    asyncio.run(main())
