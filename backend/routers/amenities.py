from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from ..database import DatabaseManager, get_database
from ..models import Amenity, AmenityCreate, AmenityUpdate, SuccessResponse, PaginatedResponse
from ..exceptions import handle_database_error, handle_not_found_error, handle_validation_error
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/amenities", tags=["Amenities"])


# Collection name constants
COLLECTION_AMENITIES = "Amenities"


@router.get("/", response_model=PaginatedResponse)
async def get_amenities(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    availability: Optional[bool] = Query(None, description="Filter by availability"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all amenities with optional filtering and pagination"""
    try:
        filter_dict = {}
        if availability is not None:
            filter_dict["availability"] = availability
        
        amenities = await db.get_documents(COLLECTION_AMENITIES, filter_dict, skip=skip, limit=limit)
        total = await db.count_documents(COLLECTION_AMENITIES, filter_dict)
        
        return PaginatedResponse(
            items=amenities,
            total=total,
            page=skip // limit + 1,
            size=limit,
            has_next=skip + limit < total,
            has_prev=skip > 0
        )
    except Exception as e:
        logger.error(f"Error getting amenities: {e}")
        raise handle_database_error(e, "retrieving amenities")

@router.get("/{amenity_id}", response_model=Amenity)
async def get_amenity(
    amenity_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get a specific amenity by ID"""
    try:
        amenity = await db.get_document(COLLECTION_AMENITIES, amenity_id)
        if not amenity:
            raise handle_not_found_error("Amenity", amenity_id)
        return amenity
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting amenity {amenity_id}: {e}")
        raise handle_database_error(e, f"retrieving amenity {amenity_id}")

@router.post("/", response_model=SuccessResponse)
async def create_amenity(
    amenity_data: AmenityCreate,
    db: DatabaseManager = Depends(get_database)
):
    """Create a new amenity"""
    try:
        # Generate amenity ID
        amenity_id = f"A-{len(await db.get_documents('amenities')) + 1:03d}"
        
        amenity_dict = amenity_data.dict()
        amenity_dict["amenity_id"] = amenity_id
        
        document_id = await db.create_document(COLLECTION_AMENITIES, amenity_dict)
        
        return SuccessResponse(
            message="Amenity created successfully",
            data={"amenity_id": amenity_id, "document_id": document_id}
        )
    except Exception as e:
        logger.error(f"Error creating amenity: {e}")
        raise handle_database_error(e, "creating amenity")

@router.put("/{amenity_id}", response_model=SuccessResponse)
async def update_amenity(
    amenity_id: str,
    amenity_data: AmenityUpdate,
    db: DatabaseManager = Depends(get_database)
):
    """Update an existing amenity"""
    try:
        # Check if amenity exists
        existing_amenity = await db.get_document(COLLECTION_AMENITIES, amenity_id)
        if not existing_amenity:
            raise handle_not_found_error("Amenity", amenity_id)
        
        # Update amenity
        update_data = amenity_data.dict(exclude_unset=True)
        success = await db.update_document(COLLECTION_AMENITIES, amenity_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="No changes were made to the amenity"
            )
        
        return SuccessResponse(
            message="Amenity updated successfully",
            data={"amenity_id": amenity_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating amenity {amenity_id}: {e}")
        raise handle_database_error(e, f"updating amenity {amenity_id}")

@router.delete("/{amenity_id}", response_model=SuccessResponse)
async def delete_amenity(
    amenity_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Delete an amenity"""
    try:
        # Check if amenity exists
        existing_amenity = await db.get_document(COLLECTION_AMENITIES, amenity_id)
        if not existing_amenity:
            raise handle_not_found_error("Amenity", amenity_id)
        
        # Delete amenity
        success = await db.delete_document(COLLECTION_AMENITIES, amenity_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to delete amenity"
            )
        
        return SuccessResponse(
            message="Amenity deleted successfully",
            data={"amenity_id": amenity_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting amenity {amenity_id}: {e}")
        raise handle_database_error(e, f"deleting amenity {amenity_id}")

@router.get("/units/{unit_id}", response_model=List[Amenity])
async def get_amenities_for_unit(
    unit_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get amenities available for a specific unit"""
    try:
        amenities = await db.get_amenities_by_units([unit_id])
        return amenities
    except Exception as e:
        logger.error(f"Error getting amenities for unit {unit_id}: {e}")
        raise handle_database_error(e, f"retrieving amenities for unit {unit_id}")

@router.get("/search/", response_model=List[Amenity])
async def search_amenities(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    db: DatabaseManager = Depends(get_database)
):
    """Search amenities by name or description"""
    try:
        amenities = await db.search_documents(COLLECTION_AMENITIES, q, ["name", "description"], limit=limit)
        return amenities
    except Exception as e:
        logger.error(f"Error searching amenities: {e}")
        raise handle_database_error(e, "searching amenities")
