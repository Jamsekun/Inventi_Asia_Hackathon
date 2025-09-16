from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from ..database import DatabaseManager, get_database
from ..models import Rent, RentCreate, RentUpdate, SuccessResponse, PaginatedResponse
from ..exceptions import handle_database_error, handle_not_found_error
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rent", tags=["Rent"])

# Collection name constants
COLLECTION_RENT = "Rent"

@router.get("/", response_model=PaginatedResponse)
async def get_rent_records(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    unit_id: Optional[str] = Query(None, description="Filter by unit ID"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    month: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}$', description="Filter by month (YYYY-MM)"),
    status: Optional[str] = Query(None, description="Filter by payment status"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all rent records with optional filtering and pagination"""
    try:
        filter_dict = {}
        if unit_id:
            filter_dict["unit_id"] = unit_id
        if tenant_id:
            filter_dict["tenant_id"] = tenant_id
        if month:
            filter_dict["month"] = month
        if status:
            filter_dict["status"] = status
        
        records = await db.get_documents(COLLECTION_RENT, filter_dict, skip=skip, limit=limit, sort_field="month", sort_order=-1)
        total = await db.count_documents(COLLECTION_RENT, filter_dict)
        
        return PaginatedResponse(
            items=records,
            total=total,
            page=skip // limit + 1,
            size=limit,
            has_next=skip + limit < total,
            has_prev=skip > 0
        )
    except Exception as e:
        logger.error(f"Error getting rent records: {e}")
        raise handle_database_error(e, "retrieving rent records")

@router.get("/{rent_id}", response_model=Rent)
async def get_rent_record(
    rent_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get a specific rent record by ID"""
    try:
        record = await db.get_document(COLLECTION_RENT, rent_id)
        if not record:
            raise handle_not_found_error("Rent Record", rent_id)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rent record {rent_id}: {e}")
        raise handle_database_error(e, f"retrieving rent record {rent_id}")

@router.post("/", response_model=SuccessResponse)
async def create_rent_record(
    rent_data: RentCreate,
    db: DatabaseManager = Depends(get_database)
):
    """Create a new rent record"""
    try:
        # Generate rent ID
        rent_id = f"R-{rent_data.month.replace('-', '-')}-{rent_data.unit_id.split('-')[1]}"
        
        rent_dict = rent_data.dict()
        rent_dict["rent_id"] = rent_id
        
        document_id = await db.create_document(COLLECTION_RENT, rent_dict)
        
        return SuccessResponse(
            message="Rent record created successfully",
            data={"rent_id": rent_id, "document_id": document_id}
        )
    except Exception as e:
        logger.error(f"Error creating rent record: {e}")
        raise handle_database_error(e, "creating rent record")

@router.put("/{rent_id}", response_model=SuccessResponse)
async def update_rent_record(
    rent_id: str,
    rent_data: RentUpdate,
    db: DatabaseManager = Depends(get_database)
):
    """Update an existing rent record"""
    try:
        # Check if record exists
        existing_record = await db.get_document(COLLECTION_RENT, rent_id)
        if not existing_record:
            raise handle_not_found_error("Rent Record", rent_id)
        
        # Update record
        update_data = rent_data.dict(exclude_unset=True)
        success = await db.update_document(COLLECTION_RENT, rent_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="No changes were made to the rent record"
            )
        
        return SuccessResponse(
            message="Rent record updated successfully",
            data={"rent_id": rent_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rent record {rent_id}: {e}")
        raise handle_database_error(e, f"updating rent record {rent_id}")

@router.delete("/{rent_id}", response_model=SuccessResponse)
async def delete_rent_record(
    rent_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Delete a rent record"""
    try:
        # Check if record exists
        existing_record = await db.get_document(COLLECTION_RENT, rent_id)
        if not existing_record:
            raise handle_not_found_error("Rent Record", rent_id)
        
        # Delete record
        success = await db.delete_document(COLLECTION_RENT, rent_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to delete rent record"
            )
        
        return SuccessResponse(
            message="Rent record deleted successfully",
            data={"rent_id": rent_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rent record {rent_id}: {e}")
        raise handle_database_error(e, f"deleting rent record {rent_id}")

@router.get("/unit/{unit_id}", response_model=List[Rent])
async def get_rent_for_unit(
    unit_id: str,
    limit: int = Query(12, ge=1, le=24, description="Number of months to retrieve"),
    db: DatabaseManager = Depends(get_database)
):
    """Get rent records for a specific unit"""
    try:
        records = await db.get_documents(COLLECTION_RENT, {"unit_id": unit_id}, limit=limit, sort_field="month", sort_order=-1)
        return records
    except Exception as e:
        logger.error(f"Error getting rent for unit {unit_id}: {e}")
        raise handle_database_error(e, f"retrieving rent for unit {unit_id}")

@router.get("/tenant/{tenant_id}", response_model=List[Rent])
async def get_rent_for_tenant(
    tenant_id: str,
    limit: int = Query(12, ge=1, le=24, description="Number of months to retrieve"),
    db: DatabaseManager = Depends(get_database)
):
    """Get rent records for a specific tenant"""
    try:
        records = await db.get_documents(COLLECTION_RENT, {"tenant_id": tenant_id}, limit=limit, sort_field="month", sort_order=-1)
        return records
    except Exception as e:
        logger.error(f"Error getting rent for tenant {tenant_id}: {e}")
        raise handle_database_error(e, f"retrieving rent for tenant {tenant_id}")

@router.get("/unit/{unit_id}/month/{month}", response_model=Rent)
async def get_rent_by_unit_and_month(
    unit_id: str,
    month: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get rent record for a specific unit and month"""
    try:
        record = await db.get_rent_by_unit_and_month(unit_id, month)
        if not record:
            raise handle_not_found_error("Rent Record", f"for unit {unit_id} in month {month}")
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rent for unit {unit_id} month {month}: {e}")
        raise handle_database_error(e, f"retrieving rent for unit {unit_id} month {month}")

@router.post("/{rent_id}/pay", response_model=SuccessResponse)
async def pay_rent(
    rent_id: str,
    payment_date: str = Query(..., regex=r'^\d{4}-\d{2}-\d{2}$', description="Payment date in YYYY-MM-DD format"),
    db: DatabaseManager = Depends(get_database)
):
    """Mark a rent record as paid"""
    try:
        # Check if record exists
        existing_record = await db.get_document(COLLECTION_RENT, rent_id)
        if not existing_record:
            raise handle_not_found_error("Rent Record", rent_id)
        
        # Update record status to paid
        success = await db.update_document(COLLECTION_RENT, rent_id, {
            "status": "paid",
            "payment_date": payment_date
        })
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to update rent payment status"
            )
        
        return SuccessResponse(
            message="Rent marked as paid",
            data={"rent_id": rent_id, "payment_date": payment_date}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error paying rent {rent_id}: {e}")
        raise handle_database_error(e, f"updating rent payment status {rent_id}")

@router.get("/unpaid/", response_model=List[Rent])
async def get_unpaid_rent(
    month: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}$', description="Filter by month (YYYY-MM)"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all unpaid rent records"""
    try:
        filter_dict = {"status": "unpaid"}
        if month:
            filter_dict["month"] = month
        
        records = await db.get_documents(COLLECTION_RENT, filter_dict, sort_field="month", sort_order=-1)
        return records
    except Exception as e:
        logger.error(f"Error getting unpaid rent: {e}")
        raise handle_database_error(e, "retrieving unpaid rent")

@router.get("/summary/monthly", response_model=dict)
async def get_monthly_rent_summary(
    year: int = Query(..., ge=2020, le=2030, description="Year to summarize"),
    db: DatabaseManager = Depends(get_database)
):
    """Get monthly rent summary for a specific year"""
    try:
        pipeline = [
            {"$match": {"month": {"$regex": f"^{year}"}}},
            {"$group": {
                "_id": "$month",
                "total_amount": {"$sum": "$amount"},
                "paid_amount": {"$sum": {"$cond": [{"$eq": ["$status", "paid"]}, "$amount", 0]}},
                "unpaid_amount": {"$sum": {"$cond": [{"$eq": ["$status", "unpaid"]}, "$amount", 0]}},
                "paid_count": {"$sum": {"$cond": [{"$eq": ["$status", "paid"]}, 1, 0]}},
                "unpaid_count": {"$sum": {"$cond": [{"$eq": ["$status", "unpaid"]}, 1, 0]}}
            }},
            {"$sort": {"_id": 1}},
            {"$project": {
                "_id": 0,
                "month": "$_id",
                "total_amount": 1,
                "paid_amount": 1,
                "unpaid_amount": 1,
                "paid_count": 1,
                "unpaid_count": 1
            }}
        ]
        
        if db.db is None:
            raise Exception("Database not initialized. Call connect() first.")
        
        summary = []
        async for doc in db.db[COLLECTION_RENT].aggregate(pipeline):
            summary.append(doc)
        
        return {"year": year, "monthly_summary": summary}
    except Exception as e:
        logger.error(f"Error getting monthly rent summary: {e}")
        raise handle_database_error(e, "retrieving monthly rent summary")
