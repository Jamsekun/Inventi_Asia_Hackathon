# backend/main.py (improved)
import os
import logging
import time
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Any, Callable, Coroutine, Dict, Tuple

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from dotenv import load_dotenv

# Load environment variables (skip in Vercel)
if os.getenv("VERCEL") is None:
    load_dotenv()

# app-specific imports
from backend.database import get_database, db_manager
from backend.Rag_System.rag3 import hybrid_generate_answer

from backend.routers import (
    amenities, contracts, bills, expenses, maintenance,
    rent, staff, tenants, units
)

from backend.models import ChatRequest, RAGResponse, PropertySummary
from backend.exceptions import (
    handle_database_error, handle_validation_error, handle_not_found_error,
    handle_conflict_error, handle_external_service_error
)

# Logging config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend.main")

# Read environment config
API_CACHE_TTL = int(os.getenv("API_CACHE_TTL_SECONDS", "30"))   # cache TTL for heavy endpoints (seconds)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
PROPERTY_API_BASE = os.getenv("PROPERTY_API_BASE", "http://localhost:8000")

# Global singletons for serverless reuse
_db_connected = False


# === Simple async TTL cache with coalescing ===
class AsyncTTLCache:
    """
    Simple async TTL cache: stores (expiry_ts, value) and prevents duplicated compute
    by using per-key asyncio.Lock to coalesce concurrent requests.
    ``get_or_compute(key, coro_func, ttl)`` expects coro_func to be a callable
    returning a coroutine (i.e., a function you can call to get the coroutine).
    """
    def __init__(self):
        self._data: Dict[str, Tuple[float, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def get(self, key: str):
        rec = self._data.get(key)
        if not rec:
            return None
        expiry, value = rec
        if time.time() > expiry:
            # expired
            async with self._global_lock:
                # double-check inside lock
                rec2 = self._data.get(key)
                if rec2 and time.time() > rec2[0]:
                    self._data.pop(key, None)
            return None
        return value

    async def get_or_compute(self, key: str, coro_func: Callable[[], Coroutine], ttl: int):
        # fast check
        v = await self.get(key)
        if v is not None:
            return v

        # ensure per-key lock exists
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            lock = self._locks[key]

        # coalesce: only one caller computes
        async with lock:
            # re-check inside lock
            v2 = await self.get(key)
            if v2 is not None:
                return v2
            # compute (coro_func returns a coroutine)
            try:
                start = time.perf_counter()
                result = await coro_func()
                elapsed = time.perf_counter() - start
                logger.info(f"[CACHE] Computed key={key} in {elapsed:.2f}s")
            except Exception as e:
                logger.exception(f"[CACHE] compute failed for key={key}: {e}")
                raise
            expiry = time.time() + ttl
            self._data[key] = (expiry, result)
            return result

    async def invalidate(self, key: str):
        async with self._global_lock:
            self._data.pop(key, None)


# instantiate cache
api_cache = AsyncTTLCache()


# === Lifespan: DB connect + optional pre-warm ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db_connected
    logger.info("Starting up Property Management API...")

    try:
        if not _db_connected or db_manager.client is None:
            await db_manager.connect()
            _db_connected = True
            logger.info("Database connection established (serverless-safe)")

        # Warm cache for heavy summaries (non-blocking awaits so startup waits for them)
        try:
            # Pre-warm property summary and bills summary but don't fail startup if these fail
            async def warm_property():
                logger.info("[WARM] Pre-warming property summary")
                return await db_manager.get_property_summary()

            async def warm_bills():
                logger.info("[WARM] Pre-warming bills summary")
                return await db_manager.get_bills_summary(None)

            # schedule warms but wait a short time (optional)
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        api_cache.get_or_compute("property_summary", lambda: warm_property(), API_CACHE_TTL),
                        api_cache.get_or_compute("bills_summary:all", lambda: warm_bills(), API_CACHE_TTL)
                    ),
                    timeout=10
                )
                logger.info("[WARM] Pre-warm completed (within 10s)")
            except asyncio.TimeoutError:
                logger.info("[WARM] Pre-warm timed out (continuing startup)")
            except Exception:
                logger.exception("[WARM] Pre-warm encountered an error (continuing startup)")

        except Exception:
            logger.exception('Failed to pre-warm caches')

    except Exception as e:
        logger.exception("Failed to initialize application")
        raise

    yield

    # shutdown
    try:
        logger.info("Shutting down Property Management API...")
        # optionally close DB connection if necessary; with serverless reuse you may keep it open
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

# CORS (read origins from env or default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handlers (keep simple)
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error", "details": "An unexpected error occurred"}
    )

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"success": False, "error": "Bad request", "details": str(exc)}
    )

# Health check
@app.get("/health")
async def health_check():
    try:
        if db_manager.client is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        # quick ping
        try:
            await db_manager.client.admin.command('ping')
            db_status = "connected"
        except Exception:
            db_status = "unreachable"
        # show cache health
        return {"status": "healthy", "database": db_status, "cache_ttl": API_CACHE_TTL}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/")
async def root():
    return {
        "message": "Property Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "collections": ["amenities", "contracts", "bills", "expenses", "maintenance", "rent", "staff", "tenants", "units"]
    }


# === RAG chat endpoint (runs blocking RAG call in threadpool so event loop not blocked) ===
@app.post("/chat", response_model=RAGResponse)
async def chat_endpoint(chat_request: ChatRequest, db=Depends(get_database)):
    try:
        # Merge user messages into single query
        user_text = "\n".join([m.content for m in chat_request.messages if m.role == 'user'])
        # optional focus
        collections = [chat_request.collection_focus] if chat_request.collection_focus else None

        # hybrid_generate_answer is sync in your RAG code; run in threadpool
        answer = await run_in_threadpool(hybrid_generate_answer, user_text)

        return RAGResponse(intent="general", response=answer, relevant_data=None)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail="Error processing chat request")


# === Property summary endpoint (cached & instrumented) ===
@app.get("/summary", response_model=PropertySummary)
async def get_property_summary(db=Depends(get_database)):
    key = "property_summary"

    async def _fetch():
        start = time.perf_counter()
        res = await db.get_property_summary()
        elapsed = time.perf_counter() - start
        logger.info(f"DB: get_property_summary executed in {elapsed:.2f}s")
        return res

    try:
        # TTL is configurable
        summary = await api_cache.get_or_compute(key, lambda: _fetch(), API_CACHE_TTL)
        return summary
    except Exception as e:
        logger.exception("Error getting property summary")
        raise handle_database_error(e, "retrieving property summary")


# === Bills summary endpoint (legacy compatibility) ===
@app.get("/summary/bills")
async def get_bills_summary_legacy(period: Optional[str] = None, db=Depends(get_database)):
    # If period not specified, use current month e.g. "2025-09"
    if not period:
        period = time.strftime("%Y-%m")

    key = f"bills_summary:{period}"

    async def _fetch():
        start = time.perf_counter()
        res = await db.get_bills_summary(period)
        elapsed = time.perf_counter() - start
        logger.info(f"DB: get_bills_summary(period={period}) executed in {elapsed:.2f}s")
        return res

    try:
        # For bills summaries we may want slightly longer TTL if desired; reuse API_CACHE_TTL
        summary = await api_cache.get_or_compute(key, lambda: _fetch(), API_CACHE_TTL)
        return summary
    except Exception as e:
        logger.exception("Error getting bills summary")
        raise handle_database_error(e, "retrieving bills summary")


# === include other routers ===
app.include_router(amenities.router)
app.include_router(contracts.router)
app.include_router(bills.router)
app.include_router(expenses.router)
app.include_router(maintenance.router)
app.include_router(rent.router)
app.include_router(staff.router)
app.include_router(tenants.router)
app.include_router(units.router)


# === Utility endpoints ===
@app.get("/collections")
async def list_collections():
    return {
        "collections": [
            {"name": "amenities", "endpoint": "/amenities"},
            {"name": "contracts", "endpoint": "/contracts"},
            {"name": "bills", "endpoint": "/bills"},
            {"name": "expenses", "endpoint": "/expenses"},
            {"name": "maintenance", "endpoint": "/maintenance"},
            {"name": "rent", "endpoint": "/rent"},
            {"name": "staff", "endpoint": "/staff"},
            {"name": "tenants", "endpoint": "/tenants"},
            {"name": "units", "endpoint": "/units"}
        ]
    }


@app.get("/intents")
async def list_rag_intents():
    return {
        "intents": [
            "AMENITIES_INFO", "CONTRACT_STATUS", "BILLING_INFO", "EXPENSES_INFO",
            "MAINTENANCE_REQUEST", "RENT_INFO", "STAFF_INFO", "TENANT_QUERY", "UNIT_INFO"
        ],
    }


@app.get("/examples")
async def get_example_queries():
    return {
        "example_queries": [
            {"intent": "AMENITIES_INFO", "examples": ["Is the swimming pool available for unit U-101?", "Which units can use the gym?"]},
            {"intent": "CONTRACT_STATUS", "examples": ["When does lease expire for tenant T-001?", "What is monthly rent for U-101?"]},
            {"intent": "BILLING_INFO", "examples": ["Latest electricity bill for U-101?", "Show me water bills for September"]},
            {"intent": "MAINTENANCE_REQUEST", "examples": ["Is the AC issue in U-101 resolved?", "What maintenance requests are pending?"]},
            {"intent": "RENT_INFO", "examples": ["Has September rent for U-101 been paid?", "Show me unpaid rent for this month"]}
        ]
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload, log_level="info")
