from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from ..database import DatabaseManager, get_database
from ..models import Tenant, TenantCreate, TenantUpdate, SuccessResponse, PaginatedResponse
from ..exceptions import handle_database_error, handle_not_found_error, TenantAlreadyAssignedException
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["Tenants"])

# Collection name constants
COLLECTION_TENANTS = "Tenants"

@router.get("/", response_model=PaginatedResponse)
async def get_tenants(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    unit_id: Optional[str] = Query(None, description="Filter by unit ID"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all tenants with optional filtering and pagination"""
    try:
        filter_dict = {}
        if unit_id:
            filter_dict["unit_id"] = unit_id
        
        tenants = await db.get_documents(COLLECTION_TENANTS, filter_dict, skip=skip, limit=limit)
        total = await db.count_documents(COLLECTION_TENANTS, filter_dict)
        
        return PaginatedResponse(
            items=tenants,
            total=total,
            page=skip // limit + 1,
            size=limit,
            has_next=skip + limit < total,
            has_prev=skip > 0
        )
    except Exception as e:
        logger.error(f"Error getting tenants: {e}")
        raise handle_database_error(e, "retrieving tenants")

@router.get("/{tenant_id}", response_model=Tenant)
async def get_tenant(
    tenant_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get a specific tenant by ID"""
    try:
        tenant = await db.get_document(COLLECTION_TENANTS, tenant_id)
        if not tenant:
            raise handle_not_found_error("Tenant", tenant_id)
        return tenant
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant {tenant_id}: {e}")
        raise handle_database_error(e, f"retrieving tenant {tenant_id}")

@router.post("/", response_model=SuccessResponse)
async def create_tenant(
    tenant_data: TenantCreate,
    db: DatabaseManager = Depends(get_database)
):
    """Create a new tenant"""
    try:
        # Check if unit is available
        unit = await db.get_document("units", tenant_data.unit_id)
        if not unit:
            raise handle_not_found_error("Unit", tenant_data.unit_id)
        
        if unit.get("status") == "occupied":
            raise HTTPException(
                status_code=409,
                detail=f"Unit {tenant_data.unit_id} is already occupied"
            )
        
        # Check if tenant is already assigned to another unit
        existing_tenant = await db.get_tenant_by_unit(tenant_data.unit_id)
        if existing_tenant:
            raise TenantAlreadyAssignedException(tenant_data.unit_id)
        
        # Generate tenant ID
        tenant_id = f"T-{len(await db.get_documents('tenants')) + 1:03d}"
        
        tenant_dict = tenant_data.dict()
        tenant_dict["tenant_id"] = tenant_id
        
        document_id = await db.create_document(COLLECTION_TENANTS, tenant_dict)
        
        # Update unit status to occupied
        await db.update_document("units", tenant_data.unit_id, {"status": "occupied", "tenant_id": tenant_id})
        
        return SuccessResponse(
            message="Tenant created successfully",
            data={"tenant_id": tenant_id, "document_id": document_id}
        )
    except (TenantAlreadyAssignedException):
        raise HTTPException(
            status_code=409,
            detail=f"Unit {tenant_data.unit_id} already has an assigned tenant"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating tenant: {e}")
        raise handle_database_error(e, "creating tenant")

@router.put("/{tenant_id}", response_model=SuccessResponse)
async def update_tenant(
    tenant_id: str,
    tenant_data: TenantUpdate,
    db: DatabaseManager = Depends(get_database)
):
    """Update an existing tenant"""
    try:
        # Check if tenant exists
        existing_tenant = await db.get_document(COLLECTION_TENANTS, tenant_id)
        if not existing_tenant:
            raise handle_not_found_error("Tenant", tenant_id)
        
        # If updating unit_id, check if new unit is available
        if tenant_data.unit_id and tenant_data.unit_id != existing_tenant.get("unit_id"):
            new_unit = await db.get_document("units", tenant_data.unit_id)
            if not new_unit:
                raise handle_not_found_error("Unit", tenant_data.unit_id)
            
            if new_unit.get("status") == "occupied":
                raise HTTPException(
                    status_code=409,
                    detail=f"Unit {tenant_data.unit_id} is already occupied"
                )
        
        # Update tenant
        update_data = tenant_data.dict(exclude_unset=True)
        success = await db.update_document(COLLECTION_TENANTS, tenant_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="No changes were made to the tenant"
            )
        
        # If unit was changed, update unit assignments
        if tenant_data.unit_id and tenant_data.unit_id != existing_tenant.get("unit_id"):
            old_unit_id = existing_tenant.get("unit_id")
            
            # Update old unit to vacant
            if old_unit_id:
                await db.update_document("units", old_unit_id, {"status": "vacant", "tenant_id": None})
            
            # Update new unit to occupied
            await db.update_document("units", tenant_data.unit_id, {"status": "occupied", "tenant_id": tenant_id})
        
        return SuccessResponse(
            message="Tenant updated successfully",
            data={"tenant_id": tenant_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tenant {tenant_id}: {e}")
        raise handle_database_error(e, f"updating tenant {tenant_id}")

@router.delete("/{tenant_id}", response_model=SuccessResponse)
async def delete_tenant(
    tenant_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Delete a tenant"""
    try:
        # Check if tenant exists
        existing_tenant = await db.get_document(COLLECTION_TENANTS, tenant_id)
        if not existing_tenant:
            raise handle_not_found_error("Tenant", tenant_id)
        
        # Update unit status to vacant
        unit_id = existing_tenant.get("unit_id")
        if unit_id:
            await db.update_document("units", unit_id, {"status": "vacant", "tenant_id": None})
        
        # Delete tenant
        success = await db.delete_document(COLLECTION_TENANTS, tenant_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to delete tenant"
            )
        
        return SuccessResponse(
            message="Tenant deleted successfully",
            data={"tenant_id": tenant_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tenant {tenant_id}: {e}")
        raise handle_database_error(e, f"deleting tenant {tenant_id}")

@router.get("/unit/{unit_id}", response_model=Tenant)
async def get_tenant_by_unit(
    unit_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get tenant for a specific unit"""
    try:
        tenant = await db.get_tenant_by_unit(unit_id)
        if not tenant:
            raise handle_not_found_error("Tenant", f"for unit {unit_id}")
        return tenant
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant for unit {unit_id}: {e}")
        raise handle_database_error(e, f"retrieving tenant for unit {unit_id}")

@router.get("/search/", response_model=List[Tenant])
async def search_tenants(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    db: DatabaseManager = Depends(get_database)
):
    """Search tenants by name, contact, or email"""
    try:
        tenants = await db.search_documents(COLLECTION_TENANTS, q, ["name", "contact", "email"], limit=limit)
        return tenants
    except Exception as e:
        logger.error(f"Error searching tenants: {e}")
        raise handle_database_error(e, "searching tenants")

@router.get("/{tenant_id}/contract", response_model=dict)
async def get_tenant_contract(
    tenant_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get contract information for a specific tenant"""
    try:
        # Check if tenant exists
        existing_tenant = await db.get_document(COLLECTION_TENANTS, tenant_id)
        if not existing_tenant:
            raise handle_not_found_error("Tenant", tenant_id)
        
        # Get contract
        contract = await db.get_contract_by_tenant(tenant_id)
        if not contract:
            raise handle_not_found_error("Contract", f"for tenant {tenant_id}")
        
        return contract
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contract for tenant {tenant_id}: {e}")
        raise handle_database_error(e, f"retrieving contract for tenant {tenant_id}")

@router.get("/{tenant_id}/bills", response_model=List[dict])
async def get_tenant_bills(
    tenant_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get all bills for a specific tenant"""
    try:
        # Check if tenant exists
        existing_tenant = await db.get_document(COLLECTION_TENANTS, tenant_id)
        if not existing_tenant:
            raise handle_not_found_error("Tenant", tenant_id)
        
        # Get unit ID
        unit_id = existing_tenant.get("unit_id")
        if not unit_id:
            return []
        
        # Get bills for the unit
        bills = await db.get_bills_by_unit(unit_id)
        return bills
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bills for tenant {tenant_id}: {e}")
        raise handle_database_error(e, f"retrieving bills for tenant {tenant_id}")

@router.get("/{tenant_id}/rent", response_model=List[dict])
async def get_tenant_rent(
    tenant_id: str,
    limit: int = Query(12, ge=1, le=24, description="Number of months to retrieve"),
    db: DatabaseManager = Depends(get_database)
):
    """Get rent records for a specific tenant"""
    try:
        # Check if tenant exists
        existing_tenant = await db.get_document(COLLECTION_TENANTS, tenant_id)
        if not existing_tenant:
            raise handle_not_found_error("Tenant", tenant_id)
        
        # Get rent records
        rent_records = await db.get_documents("rent", {"tenant_id": tenant_id}, limit=limit, sort_field="month", sort_order=-1)
        return rent_records
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rent for tenant {tenant_id}: {e}")
        raise handle_database_error(e, f"retrieving rent for tenant {tenant_id}")

@router.get("/{tenant_id}/maintenance", response_model=List[dict])
async def get_tenant_maintenance(
    tenant_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get maintenance requests for a specific tenant"""
    try:
        # Check if tenant exists
        existing_tenant = await db.get_document(COLLECTION_TENANTS, tenant_id)
        if not existing_tenant:
            raise handle_not_found_error("Tenant", tenant_id)
        
        # Get unit ID
        unit_id = existing_tenant.get("unit_id")
        if not unit_id:
            return []
        
        # Get maintenance requests for the unit
        maintenance_requests = await db.get_maintenance_by_unit(unit_id)
        return maintenance_requests
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting maintenance for tenant {tenant_id}: {e}")
        raise handle_database_error(e, f"retrieving maintenance for tenant {tenant_id}")
