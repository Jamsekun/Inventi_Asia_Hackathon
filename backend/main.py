import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()

# Import database and RAG system
from backend.database import get_database, db_manager
from backend.rag_system import RAGSystem

# Import all routers
from backend.routers import (
    amenities, contracts, bills, expenses, maintenance, 
    rent, staff, tenants, units
)

# Import models
from backend.models import ChatRequest, RAGResponse, PropertySummary

# Import exception handlers
from backend.exceptions import (
    handle_database_error, handle_validation_error, handle_not_found_error,
    handle_conflict_error, handle_external_service_error
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global RAG system instance
rag_system: Optional[RAGSystem] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting up Property Management API...")
    
    try:
        # Initialize database connection
        await db_manager.connect()
        logger.info("Database connection established")
        
        # Initialize RAG system
        global rag_system
        rag_system = RAGSystem(db_manager)
        await rag_system.initialize()
        logger.info("RAG system initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Property Management API...")
    try:
        await db_manager.disconnect()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Create FastAPI app
app = FastAPI(
    title="Property Management API",
    description="A comprehensive property management system with RAG-powered intelligent queries",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "details": "An unexpected error occurred"
        }
    )

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Value error handler"""
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": "Bad request",
            "details": str(exc)
        }
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        if db_manager.client is None:
            raise HTTPException(
                status_code=503,
                detail="Database not connected"
            )
        
        await db_manager.client.admin.command('ping')
        return {
            "status": "healthy",
            "database": "connected",
            "rag_system": "initialized" if rag_system else "not_initialized"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service unhealthy"
        )

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Property Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "collections": [
            "amenities", "contracts", "bills", "expenses", "maintenance",
            "rent", "staff", "tenants", "units"
        ],
        "features": [
            "CRUD operations for all collections",
            "RAG-powered intelligent queries",
            "Comprehensive error handling",
            "Data validation and filtering",
            "Pagination support",
            "Search functionality"
        ]
    }

# RAG Chat endpoint
@app.post("/chat", response_model=RAGResponse)
async def chat_endpoint(
    chat_request: ChatRequest,
    db=Depends(get_database)
):
    """RAG-powered chat endpoint for intelligent property management queries"""
    try:
        if not rag_system:
            raise HTTPException(
                status_code=503,
                detail="RAG system not initialized"
            )
        
        # Process the query using RAG system
        response = await rag_system.process_query(chat_request)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error processing chat request"
        )

# Property summary endpoint
@app.get("/summary", response_model=PropertySummary)
async def get_property_summary(db=Depends(get_database)):
    """Get overall property management summary"""
    try:
        summary = await db.get_property_summary()
        return summary
    except Exception as e:
        logger.error(f"Error getting property summary: {e}")
        raise handle_database_error(e, "retrieving property summary")

# Bills summary endpoint (legacy compatibility)
@app.get("/summary/bills")
async def get_bills_summary_legacy(
    period: str = "2025-09",
    db=Depends(get_database)
):
    """Legacy bills summary endpoint for backward compatibility"""
    try:
        summary = await db.get_bills_summary(period)
        return summary
    except Exception as e:
        logger.error(f"Error getting bills summary: {e}")
        raise handle_database_error(e, "retrieving bills summary")

# Include all routers
app.include_router(amenities.router)
app.include_router(contracts.router)
app.include_router(bills.router)
app.include_router(expenses.router)
app.include_router(maintenance.router)
app.include_router(rent.router)
app.include_router(staff.router)
app.include_router(tenants.router)
app.include_router(units.router)

# Additional utility endpoints
@app.get("/collections")
async def list_collections():
    """List all available collections"""
    return {
        "collections": [
            {
                "name": "amenities",
                "description": "Property amenities and facilities",
                "endpoint": "/amenities"
            },
            {
                "name": "contracts",
                "description": "Tenant lease contracts",
                "endpoint": "/contracts"
            },
            {
                "name": "bills",
                "description": "Electric and water bills",
                "endpoint": "/bills"
            },
            {
                "name": "expenses",
                "description": "Property maintenance expenses",
                "endpoint": "/expenses"
            },
            {
                "name": "maintenance",
                "description": "Maintenance requests and issues",
                "endpoint": "/maintenance"
            },
            {
                "name": "rent",
                "description": "Rent payment records",
                "endpoint": "/rent"
            },
            {
                "name": "staff",
                "description": "Property management staff",
                "endpoint": "/staff"
            },
            {
                "name": "tenants",
                "description": "Tenant information",
                "endpoint": "/tenants"
            },
            {
                "name": "units",
                "description": "Property units and their status",
                "endpoint": "/units"
            }
        ]
    }

@app.get("/intents")
async def list_rag_intents():
    """List all supported RAG intents"""
    if not rag_system:
        raise HTTPException(
            status_code=503,
            detail="RAG system not initialized"
        )
    
    return {
        "intents": list(rag_system.intent_patterns.keys()),
        "descriptions": {
            "AMENITIES_INFO": "Queries about property amenities, facilities, and availability",
            "CONTRACT_STATUS": "Queries about lease contracts, terms, and expiration",
            "BILLING_INFO": "Queries about electricity and water bills",
            "EXPENSES_INFO": "Queries about property maintenance expenses",
            "MAINTENANCE_REQUEST": "Queries about maintenance requests and issues",
            "RENT_INFO": "Queries about rent payments and records",
            "STAFF_INFO": "Queries about property management staff",
            "TENANT_QUERY": "Queries about tenant information and details",
            "UNIT_INFO": "Queries about property units and their status"
        }
    }

# Example queries endpoint
@app.get("/examples")
async def get_example_queries():
    """Get example queries for the RAG system"""
    return {
        "example_queries": [
            {
                "intent": "AMENITIES_INFO",
                "examples": [
                    "Is the swimming pool available for unit U-101?",
                    "Which units can use the gym?",
                    "Pwede ba gamitin yung function hall today?"
                ]
            },
            {
                "intent": "CONTRACT_STATUS",
                "examples": [
                    "When does the lease expire for tenant T-001?",
                    "What is the monthly rent for unit U-101?",
                    "Kailan mag-e-expire yung contract sa U-202?"
                ]
            },
            {
                "intent": "BILLING_INFO",
                "examples": [
                    "What is the latest electricity bill for unit U-101?",
                    "Show me the water bills for September",
                    "Magkano ang SOA ng kuryente ng U-201?"
                ]
            },
            {
                "intent": "MAINTENANCE_REQUEST",
                "examples": [
                    "Is the aircon issue in unit U-101 resolved?",
                    "What maintenance requests are pending?",
                    "Naayos na ba yung elevator repair?"
                ]
            },
            {
                "intent": "RENT_INFO",
                "examples": [
                    "Has the September rent for unit U-101 been paid?",
                    "Show me unpaid rent for this month",
                    "Nabayaran na ba ang rent ng U-202?"
                ]
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )