from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from ..database import DatabaseManager, get_database
from ..models import Staff, StaffCreate, StaffUpdate, SuccessResponse, PaginatedResponse
from ..exceptions import handle_database_error, handle_not_found_error
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/staff", tags=["Staff"])

# Collection name constants
COLLECTION_STAFF = "Staff"

@router.get("/", response_model=PaginatedResponse)
async def get_staff(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    role: Optional[str] = Query(None, description="Filter by staff role"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all staff members with optional filtering and pagination"""
    try:
        filter_dict = {}
        if role:
            filter_dict["role"] = role
        
        staff = await db.get_documents(COLLECTION_STAFF, filter_dict, skip=skip, limit=limit)
        total = await db.count_documents(COLLECTION_STAFF, filter_dict)
        
        return PaginatedResponse(
            items=staff,
            total=total,
            page=skip // limit + 1,
            size=limit,
            has_next=skip + limit < total,
            has_prev=skip > 0
        )
    except Exception as e:
        logger.error(f"Error getting staff: {e}")
        raise handle_database_error(e, "retrieving staff")

@router.get("/{staff_id}", response_model=Staff)
async def get_staff_member(
    staff_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get a specific staff member by ID"""
    try:
        staff_member = await db.get_document(COLLECTION_STAFF, staff_id)
        if not staff_member:
            raise handle_not_found_error("Staff", staff_id)
        return staff_member
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting staff member {staff_id}: {e}")
        raise handle_database_error(e, f"retrieving staff member {staff_id}")

@router.post("/", response_model=SuccessResponse)
async def create_staff_member(
    staff_data: StaffCreate,
    db: DatabaseManager = Depends(get_database)
):
    """Create a new staff member"""
    try:
        # Generate staff ID
        staff_id = f"S-{len(await db.get_documents('staff')) + 1:03d}"
        
        staff_dict = staff_data.dict()
        staff_dict["staff_id"] = staff_id
        
        document_id = await db.create_document(COLLECTION_STAFF, staff_dict)
        
        return SuccessResponse(
            message="Staff member created successfully",
            data={"staff_id": staff_id, "document_id": document_id}
        )
    except Exception as e:
        logger.error(f"Error creating staff member: {e}")
        raise handle_database_error(e, "creating staff member")

@router.put("/{staff_id}", response_model=SuccessResponse)
async def update_staff_member(
    staff_id: str,
    staff_data: StaffUpdate,
    db: DatabaseManager = Depends(get_database)
):
    """Update an existing staff member"""
    try:
        # Check if staff member exists
        existing_staff = await db.get_document(COLLECTION_STAFF, staff_id)
        if not existing_staff:
            raise handle_not_found_error("Staff Member", staff_id)
        
        # Update staff member
        update_data = staff_data.dict(exclude_unset=True)
        success = await db.update_document(COLLECTION_STAFF, staff_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="No changes were made to the staff member"
            )
        
        return SuccessResponse(
            message="Staff member updated successfully",
            data={"staff_id": staff_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating staff member {staff_id}: {e}")
        raise handle_database_error(e, f"updating staff member {staff_id}")

@router.delete("/{staff_id}", response_model=SuccessResponse)
async def delete_staff_member(
    staff_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Delete a staff member"""
    try:
        # Check if staff member exists
        existing_staff = await db.get_document(COLLECTION_STAFF, staff_id)
        if not existing_staff:
            raise handle_not_found_error("Staff Member", staff_id)
        
        # Delete staff member
        success = await db.delete_document(COLLECTION_STAFF, staff_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to delete staff member"
            )
        
        return SuccessResponse(
            message="Staff member deleted successfully",
            data={"staff_id": staff_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting staff member {staff_id}: {e}")
        raise handle_database_error(e, f"deleting staff member {staff_id}")

@router.get("/role/{role}", response_model=List[Staff])
async def get_staff_by_role(
    role: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get all staff members by role"""
    try:
        staff = await db.get_documents(COLLECTION_STAFF, {"role": role})
        return staff
    except Exception as e:
        logger.error(f"Error getting staff by role {role}: {e}")
        raise handle_database_error(e, f"retrieving staff by role {role}")

@router.get("/roles/", response_model=List[str])
async def get_staff_roles(
    db: DatabaseManager = Depends(get_database)
):
    """Get all unique staff roles"""
    try:
        pipeline = [
            {"$group": {"_id": "$role"}},
            {"$sort": {"_id": 1}},
            {"$project": {"_id": 0, "role": "$_id"}}
        ]
        
        if db.db is None:
            raise Exception("Database not initialized. Call connect() first.")
        
        roles = []
        async for doc in db.db[COLLECTION_STAFF].aggregate(pipeline):
            roles.append(doc["role"])
        
        return roles
    except Exception as e:
        logger.error(f"Error getting staff roles: {e}")
        raise handle_database_error(e, "retrieving staff roles")

@router.get("/{staff_id}/assignments", response_model=List[dict])
async def get_staff_assignments(
    staff_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get maintenance assignments for a specific staff member"""
    try:
        # Check if staff member exists
        existing_staff = await db.get_document(COLLECTION_STAFF, staff_id)
        if not existing_staff:
            raise handle_not_found_error("Staff Member", staff_id)
        
        assigned_requests = existing_staff.get("assigned_requests", [])
        
        # Get details of assigned maintenance requests
        assignments = []
        for request_id in assigned_requests:
            request = await db.get_document("maintenance", request_id)
            if request:
                assignments.append(request)
        
        return assignments
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting staff assignments for {staff_id}: {e}")
        raise handle_database_error(e, f"retrieving staff assignments for {staff_id}")

@router.post("/{staff_id}/assign/{request_id}", response_model=SuccessResponse)
async def assign_maintenance_request(
    staff_id: str,
    request_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Assign a maintenance request to a staff member"""
    try:
        # Check if staff member exists
        existing_staff = await db.get_document(COLLECTION_STAFF, staff_id)
        if not existing_staff:
            raise handle_not_found_error("Staff Member", staff_id)
        
        # Check if maintenance request exists
        existing_request = await db.get_document("maintenance", request_id)
        if not existing_request:
            raise handle_not_found_error("Maintenance Request", request_id)
        
        # Add request to staff assignments
        current_assignments = existing_staff.get("assigned_requests", [])
        if request_id not in current_assignments:
            current_assignments.append(request_id)
            success = await db.update_document(COLLECTION_STAFF, staff_id, {"assigned_requests": current_assignments})
            
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to assign maintenance request"
                )
        
        return SuccessResponse(
            message="Maintenance request assigned successfully",
            data={"staff_id": staff_id, "request_id": request_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning maintenance request {request_id} to staff {staff_id}: {e}")
        raise handle_database_error(e, f"assigning maintenance request {request_id} to staff {staff_id}")

@router.delete("/{staff_id}/unassign/{request_id}", response_model=SuccessResponse)
async def unassign_maintenance_request(
    staff_id: str,
    request_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Unassign a maintenance request from a staff member"""
    try:
        # Check if staff member exists
        existing_staff = await db.get_document(COLLECTION_STAFF, staff_id)
        if not existing_staff:
            raise handle_not_found_error("Staff Member", staff_id)
        
        # Remove request from staff assignments
        current_assignments = existing_staff.get("assigned_requests", [])
        if request_id in current_assignments:
            current_assignments.remove(request_id)
            success = await db.update_document(COLLECTION_STAFF, staff_id, {"assigned_requests": current_assignments})
            
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to unassign maintenance request"
                )
        
        return SuccessResponse(
            message="Maintenance request unassigned successfully",
            data={"staff_id": staff_id, "request_id": request_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unassigning maintenance request {request_id} from staff {staff_id}: {e}")
        raise handle_database_error(e, f"unassigning maintenance request {request_id} from staff {staff_id}")

@router.get("/summary/", response_model=dict)
async def get_staff_summary(
    db: DatabaseManager = Depends(get_database)
):
    """Get staff summary statistics"""
    try:
        pipeline = [
            {"$group": {
                "_id": "$role",
                "count": {"$sum": 1},
                "total_assignments": {"$sum": {"$size": "$assigned_requests"}}
            }},
            {"$sort": {"count": -1}},
            {"$project": {
                "_id": 0,
                "role": "$_id",
                "count": 1,
                "total_assignments": 1
            }}
        ]
        
        if db.db is None:
            raise Exception("Database not initialized. Call connect() first.")
        
        summary = []
        async for doc in db.db[COLLECTION_STAFF].aggregate(pipeline):
            summary.append(doc)
        
        total_staff = sum(item["count"] for item in summary)
        total_assignments = sum(item["total_assignments"] for item in summary)
        
        return {
            "total_staff": total_staff,
            "total_assignments": total_assignments,
            "by_role": summary
        }
    except Exception as e:
        logger.error(f"Error getting staff summary: {e}")
        raise handle_database_error(e, "retrieving staff summary")
