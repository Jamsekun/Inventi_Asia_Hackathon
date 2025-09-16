from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Any
from ..database import DatabaseManager, get_database
from ..models import Unit, UnitCreate, UnitUpdate, SuccessResponse, PaginatedResponse
from ..exceptions import handle_database_error, handle_not_found_error, UnitOccupiedException
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/units", tags=["Units"])

# Collection name constants
COLLECTION_UNITS = "Units"
COLLECTION_TENANTS = "Tenants"


@router.get("/", response_model=PaginatedResponse)
async def get_units(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    floor: Optional[int] = Query(None, ge=1, description="Filter by floor number"),
    status: Optional[str] = Query(None, description="Filter by unit status"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all units with optional filtering and pagination"""
    try:
        filter_dict: dict[str, Any] = {}
        if floor is not None:
            filter_dict["floor"] = floor
        if status:
            filter_dict["status"] = status
        
        units = await db.get_documents(COLLECTION_UNITS, filter_dict, skip=skip, limit=limit, sort_field="unit_id")
        total = await db.count_documents(COLLECTION_UNITS, filter_dict)
        
        return PaginatedResponse(
            items=units,
            total=total,
            page=skip // limit + 1,
            size=limit,
            has_next=skip + limit < total,
            has_prev=skip > 0
        )
    except Exception as e:
        logger.error(f"Error getting units: {e}")
        raise handle_database_error(e, "retrieving units")

@router.get("/{unit_id}", response_model=Unit)
async def get_unit(
    unit_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get a specific unit by ID"""
    try:
        unit = await db.get_document(COLLECTION_UNITS, unit_id)
        if not unit:
            raise handle_not_found_error(COLLECTION_UNITS, unit_id)
        return unit
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting unit {unit_id}: {e}")
        raise handle_database_error(e, f"retrieving unit {unit_id}")

@router.post("/", response_model=SuccessResponse)
async def create_unit(
    unit_data: UnitCreate,
    db: DatabaseManager = Depends(get_database)
):
    """Create a new unit"""
    try:
        # Check if unit number already exists on the same floor
        existing_unit = await db.get_documents(COLLECTION_UNITS, {"floor": unit_data.floor, "number": unit_data.number})
        if existing_unit:
            raise HTTPException(
                status_code=409,
                detail=f"Unit {unit_data.number} already exists on floor {unit_data.floor}"
            )
        
        # Generate unit ID
        unit_id = f"U-{unit_data.floor:02d}{unit_data.number}"
        
        unit_dict = unit_data.dict()
        unit_dict["unit_id"] = unit_id
        
        document_id = await db.create_document(COLLECTION_UNITS, unit_dict)
        
        return SuccessResponse(
            message="Unit created successfully",
            data={"unit_id": unit_id, "document_id": document_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating unit: {e}")
        raise handle_database_error(e, "creating unit")

@router.put("/{unit_id}", response_model=SuccessResponse)
async def update_unit(
    unit_id: str,
    unit_data: UnitUpdate,
    db: DatabaseManager = Depends(get_database)
):
    """Update an existing unit"""
    try:
        # Check if unit exists
        existing_unit = await db.get_document(COLLECTION_UNITS, unit_id)
        if not existing_unit:
            raise handle_not_found_error(COLLECTION_UNITS, unit_id)
        
        # Check if changing from occupied to vacant is allowed
        if (unit_data.status == "vacant" and 
            existing_unit.get("status") == "occupied" and 
            existing_unit.get("tenant_id")):
            raise HTTPException(
                status_code=400,
                detail="Cannot change occupied unit to vacant while tenant is assigned. Please remove tenant first."
            )
        
        # Update unit
        update_data = unit_data.dict(exclude_unset=True)
        success = await db.update_document(COLLECTION_UNITS, unit_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="No changes were made to the unit"
            )
        
        return SuccessResponse(
            message="Unit updated successfully",
            data={"unit_id": unit_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating unit {unit_id}: {e}")
        raise handle_database_error(e, f"updating unit {unit_id}")

@router.delete("/{unit_id}", response_model=SuccessResponse)
async def delete_unit(
    unit_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Delete a unit"""
    try:
        # Check if unit exists
        existing_unit = await db.get_document(COLLECTION_UNITS, unit_id)
        if not existing_unit:
            raise handle_not_found_error(COLLECTION_UNITS, unit_id)
        
        # Check if unit is occupied
        if existing_unit.get("status") == "occupied":
            raise UnitOccupiedException(unit_id)
        
        # Delete unit
        success = await db.delete_document(COLLECTION_UNITS, unit_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to delete unit"
            )
        
        return SuccessResponse(
            message="Unit deleted successfully",
            data={"unit_id": unit_id}
        )
    except UnitOccupiedException:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete occupied unit {unit_id}. Please remove tenant first."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting unit {unit_id}: {e}")
        raise handle_database_error(e, f"deleting unit {unit_id}")

@router.get("/floor/{floor}", response_model=List[Unit])
async def get_units_by_floor(
    floor: int,
    db: DatabaseManager = Depends(get_database)
):
    """Get all units on a specific floor"""
    try:
        units = await db.get_documents(COLLECTION_UNITS, {"floor": floor}, sort_field="number")
        return units
    except Exception as e:
        logger.error(f"Error getting units for floor {floor}: {e}")
        raise handle_database_error(e, f"retrieving units for floor {floor}")

@router.get("/available/", response_model=List[Unit])
async def get_available_units(
    floor: Optional[int] = Query(None, ge=1, description="Filter by floor number"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all available (vacant) units"""
    try:
        filter_dict: dict[str, Any] = {"status": "vacant"}
        if floor is not None:
            filter_dict["floor"] = floor
        
        units = await db.get_documents(COLLECTION_UNITS, filter_dict, sort_field="unit_id")
        return units
    except Exception as e:
        logger.error(f"Error getting available units: {e}")
        raise handle_database_error(e, "retrieving available units")

@router.get("/occupied/", response_model=List[Unit])
async def get_occupied_units(
    floor: Optional[int] = Query(None, ge=1, description="Filter by floor number"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all occupied units"""
    try:
        filter_dict: dict[str, Any] = {"status": "occupied"}
        if floor is not None:
            filter_dict["floor"] = floor
        
        units = await db.get_documents(COLLECTION_UNITS, filter_dict, sort_field="unit_id")
        return units
    except Exception as e:
        logger.error(f"Error getting occupied units: {e}")
        raise handle_database_error(e, "retrieving occupied units")

@router.get("/{unit_id}/tenant", response_model=dict)
async def get_unit_tenant(
    unit_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get tenant information for a specific unit"""
    try:
        # Check if unit exists
        existing_unit = await db.get_document(COLLECTION_UNITS, unit_id)
        if not existing_unit:
            raise handle_not_found_error(COLLECTION_UNITS, unit_id)
        
        # Get tenant
        tenant_id = existing_unit.get("tenant_id")
        if not tenant_id:
            raise handle_not_found_error(COLLECTION_TENANTS, f"for unit {unit_id}")
        
        tenant = await db.get_document("tenants", tenant_id)
        if not tenant:
            raise handle_not_found_error(COLLECTION_TENANTS, tenant_id)
        
        return tenant
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant for unit {unit_id}: {e}")
        raise handle_database_error(e, f"retrieving tenant for unit {unit_id}")

@router.get("/{unit_id}/bills", response_model=List[dict])
async def get_unit_bills(
    unit_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get all bills for a specific unit"""
    try:
        # Check if unit exists
        existing_unit = await db.get_document(COLLECTION_UNITS, unit_id)
        if not existing_unit:
            raise handle_not_found_error(COLLECTION_UNITS, unit_id)
        
        # Get bills for the unit
        bills = await db.get_bills_by_unit(unit_id)
        return bills
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bills for unit {unit_id}: {e}")
        raise handle_database_error(e, f"retrieving bills for unit {unit_id}")

@router.get("/{unit_id}/maintenance", response_model=List[dict])
async def get_unit_maintenance(
    unit_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get maintenance requests for a specific unit"""
    try:
        # Check if unit exists
        existing_unit = await db.get_document(COLLECTION_UNITS, unit_id)
        if not existing_unit:
            raise handle_not_found_error(COLLECTION_UNITS, unit_id)
        
        # Get maintenance requests for the unit
        maintenance_requests = await db.get_maintenance_by_unit(unit_id)
        return maintenance_requests
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting maintenance for unit {unit_id}: {e}")
        raise handle_database_error(e, f"retrieving maintenance for unit {unit_id}")

@router.get("/{unit_id}/amenities", response_model=List[dict])
async def get_unit_amenities(
    unit_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get amenities available for a specific unit"""
    try:
        # Check if unit exists
        existing_unit = await db.get_document(COLLECTION_UNITS, unit_id)
        if not existing_unit:
            raise handle_not_found_error(COLLECTION_UNITS, unit_id)
        
        # Get amenities for the unit
        amenities = await db.get_amenities_by_units([unit_id])
        return amenities
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting amenities for unit {unit_id}: {e}")
        raise handle_database_error(e, f"retrieving amenities for unit {unit_id}")

@router.get("/summary/", response_model=dict)
async def get_units_summary(
    db: DatabaseManager = Depends(get_database)
):
    """Get units summary statistics"""
    try:
        pipeline = [
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }},
            {"$project": {
                "_id": 0,
                "status": "$_id",
                "count": 1
            }}
        ]
        
        if db.db is None:
            raise Exception("Database not initialized. Call connect() first.")
        
        summary = []
        async for doc in db.db[COLLECTION_UNITS].aggregate(pipeline):
            summary.append(doc)
        
        total_units = sum(item["count"] for item in summary)
        
        # Get floor distribution
        floor_pipeline = [
            {"$group": {
                "_id": "$floor",
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}},
            {"$project": {
                "_id": 0,
                "floor": "$_id",
                "count": 1
            }}
        ]
        
        floor_summary = []
        async for doc in db.db[COLLECTION_UNITS].aggregate(floor_pipeline):
            floor_summary.append(doc)
        
        return {
            "total_units": total_units,
            "by_status": summary,
            "by_floor": floor_summary
        }
    except Exception as e:
        logger.error(f"Error getting units summary: {e}")
        raise handle_database_error(e, "retrieving units summary")
