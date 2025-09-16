from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from ..database import DatabaseManager, get_database
from ..models import Maintenance, MaintenanceCreate, MaintenanceUpdate, SuccessResponse, PaginatedResponse
from ..exceptions import handle_database_error, handle_not_found_error, MaintenanceAlreadyResolvedException
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])

# Collection name constants
COLLECTION_MAINTENANCE = "Maintenance"

@router.get("/", response_model=PaginatedResponse)
async def get_maintenance_requests(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    unit_id: Optional[str] = Query(None, description="Filter by unit ID"),
    status: Optional[str] = Query(None, description="Filter by request status"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all maintenance requests with optional filtering and pagination"""
    try:
        filter_dict = {}
        if unit_id:
            filter_dict["unit_id"] = unit_id
        if status:
            filter_dict["status"] = status
        
        requests = await db.get_documents(COLLECTION_MAINTENANCE, filter_dict, skip=skip, limit=limit, sort_field="reported_date", sort_order=-1)
        total = await db.count_documents(COLLECTION_MAINTENANCE, filter_dict)
        
        return PaginatedResponse(
            items=requests,
            total=total,
            page=skip // limit + 1,
            size=limit,
            has_next=skip + limit < total,
            has_prev=skip > 0
        )
    except Exception as e:
        logger.error(f"Error getting maintenance requests: {e}")
        raise handle_database_error(e, "retrieving maintenance requests")

@router.get("/{request_id}", response_model=Maintenance)
async def get_maintenance_request(
    request_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get a specific maintenance request by ID"""
    try:
        request = await db.get_document(COLLECTION_MAINTENANCE, request_id)
        if not request:
            raise handle_not_found_error("Maintenance Request", request_id)
        return request
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting maintenance request {request_id}: {e}")
        raise handle_database_error(e, f"retrieving maintenance request {request_id}")

@router.post("/", response_model=SuccessResponse)
async def create_maintenance_request(
    request_data: MaintenanceCreate,
    db: DatabaseManager = Depends(get_database)
):
    """Create a new maintenance request"""
    try:
        # Generate request ID
        request_id = f"M-{request_data.unit_id.split('-')[1]}-{request_data.reported_date.replace('-', '-')}-{len(await db.get_documents('maintenance')) + 1:02d}"
        
        request_dict = request_data.dict()
        request_dict["request_id"] = request_id
        
        document_id = await db.create_document(COLLECTION_MAINTENANCE, request_dict)
        
        return SuccessResponse(
            message="Maintenance request created successfully",
            data={"request_id": request_id, "document_id": document_id}
        )
    except Exception as e:
        logger.error(f"Error creating maintenance request: {e}")
        raise handle_database_error(e, "creating maintenance request")

@router.put("/{request_id}", response_model=SuccessResponse)
async def update_maintenance_request(
    request_id: str,
    request_data: MaintenanceUpdate,
    db: DatabaseManager = Depends(get_database)
):
    """Update an existing maintenance request"""
    try:
        # Check if request exists
        existing_request = await db.get_document(COLLECTION_MAINTENANCE, request_id)
        if not existing_request:
            raise handle_not_found_error("Maintenance Request", request_id)
        
        # Update request
        update_data = request_data.dict(exclude_unset=True)
        success = await db.update_document(COLLECTION_MAINTENANCE, request_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="No changes were made to the maintenance request"
            )
        
        return SuccessResponse(
            message="Maintenance request updated successfully",
            data={"request_id": request_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating maintenance request {request_id}: {e}")
        raise handle_database_error(e, f"updating maintenance request {request_id}")

@router.delete("/{request_id}", response_model=SuccessResponse)
async def delete_maintenance_request(
    request_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Delete a maintenance request"""
    try:
        # Check if request exists
        existing_request = await db.get_document(COLLECTION_MAINTENANCE, request_id)
        if not existing_request:
            raise handle_not_found_error("Maintenance Request", request_id)
        
        # Delete request
        success = await db.delete_document(COLLECTION_MAINTENANCE, request_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to delete maintenance request"
            )
        
        return SuccessResponse(
            message="Maintenance request deleted successfully",
            data={"request_id": request_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting maintenance request {request_id}: {e}")
        raise handle_database_error(e, f"deleting maintenance request {request_id}")

@router.get("/unit/{unit_id}", response_model=List[Maintenance])
async def get_maintenance_for_unit(
    unit_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get all maintenance requests for a specific unit"""
    try:
        requests = await db.get_maintenance_by_unit(unit_id)
        return requests
    except Exception as e:
        logger.error(f"Error getting maintenance for unit {unit_id}: {e}")
        raise handle_database_error(e, f"retrieving maintenance for unit {unit_id}")

@router.post("/{request_id}/resolve", response_model=SuccessResponse)
async def resolve_maintenance_request(
    request_id: str,
    resolved_date: str = Query(..., regex=r'^\d{4}-\d{2}-\d{2}$', description="Resolution date in YYYY-MM-DD format"),
    db: DatabaseManager = Depends(get_database)
):
    """Mark a maintenance request as resolved"""
    try:
        # Check if request exists
        existing_request = await db.get_document(COLLECTION_MAINTENANCE, request_id)
        if not existing_request:
            raise handle_not_found_error("Maintenance Request", request_id)
        
        # Check if already resolved
        if existing_request.get("status") == "resolved":
            raise MaintenanceAlreadyResolvedException(request_id)
        
        # Update request status to resolved
        success = await db.update_document(COLLECTION_MAINTENANCE, request_id, {
            "status": "resolved",
            "resolved_date": resolved_date
        })
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to resolve maintenance request"
            )
        
        return SuccessResponse(
            message="Maintenance request resolved successfully",
            data={"request_id": request_id, "resolved_date": resolved_date}
        )
    except MaintenanceAlreadyResolvedException:
        raise HTTPException(
            status_code=400,
            detail=f"Maintenance request {request_id} is already resolved"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving maintenance request {request_id}: {e}")
        raise handle_database_error(e, f"resolving maintenance request {request_id}")

@router.get("/pending/", response_model=List[Maintenance])
async def get_pending_maintenance(
    db: DatabaseManager = Depends(get_database)
):
    """Get all pending maintenance requests"""
    try:
        requests = await db.get_documents(COLLECTION_MAINTENANCE, {"status": "pending"})
        return requests
    except Exception as e:
        logger.error(f"Error getting pending maintenance requests: {e}")
        raise handle_database_error(e, "retrieving pending maintenance requests")

@router.get("/resolved/", response_model=List[Maintenance])
async def get_resolved_maintenance(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all resolved maintenance requests"""
    try:
        requests = await db.get_documents(COLLECTION_MAINTENANCE, {"status": "resolved"}, skip=skip, limit=limit, sort_field="resolved_date", sort_order=-1)
        return requests
    except Exception as e:
        logger.error(f"Error getting resolved maintenance requests: {e}")
        raise handle_database_error(e, "retrieving resolved maintenance requests")

@router.get("/summary/", response_model=dict)
async def get_maintenance_summary(
    db: DatabaseManager = Depends(get_database)
):
    """Get maintenance summary statistics"""
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
        async for doc in db.db[COLLECTION_MAINTENANCE].aggregate(pipeline):
            summary.append(doc)
        
        total_requests = sum(item["count"] for item in summary)
        
        return {
            "total_requests": total_requests,
            "by_status": summary
        }
    except Exception as e:
        logger.error(f"Error getting maintenance summary: {e}")
        raise handle_database_error(e, "retrieving maintenance summary")
