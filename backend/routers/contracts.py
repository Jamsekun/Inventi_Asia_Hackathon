from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from ..database import DatabaseManager, get_database
from ..models import Contract, ContractCreate, ContractUpdate, SuccessResponse, PaginatedResponse
from ..exceptions import (
    handle_database_error, handle_not_found_error, handle_conflict_error,
    UnitOccupiedException, TenantAlreadyAssignedException, ContractExpiredException
)
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts", tags=["Contracts"])

# Collection name constants
COLLECTION_CONTRACTS = "Contracts"

@router.get("/", response_model=PaginatedResponse)
async def get_contracts(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    status: Optional[str] = Query(None, description="Filter by contract status"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    unit_id: Optional[str] = Query(None, description="Filter by unit ID"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all contracts with optional filtering and pagination"""
    try:
        filter_dict = {}
        if status:
            filter_dict["status"] = status
        if tenant_id:
            filter_dict["tenant_id"] = tenant_id
        if unit_id:
            filter_dict["unit_id"] = unit_id
        
        contracts = await db.get_documents(COLLECTION_CONTRACTS, filter_dict, skip=skip, limit=limit)
        total = await db.count_documents(COLLECTION_CONTRACTS, filter_dict)
        
        return PaginatedResponse(
            items=contracts,
            total=total,
            page=skip // limit + 1,
            size=limit,
            has_next=skip + limit < total,
            has_prev=skip > 0
        )
    except Exception as e:
        logger.error(f"Error getting contracts: {e}")
        raise handle_database_error(e, "retrieving contracts")

@router.get("/{contract_id}", response_model=Contract)
async def get_contract(
    contract_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get a specific contract by ID"""
    try:
        contract = await db.get_document(COLLECTION_CONTRACTS, contract_id)
        if not contract:
            raise handle_not_found_error("Contract", contract_id)
        return contract
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contract {contract_id}: {e}")
        raise handle_database_error(e, f"retrieving contract {contract_id}")

@router.post("/", response_model=SuccessResponse)
async def create_contract(
    contract_data: ContractCreate,
    db: DatabaseManager = Depends(get_database)
):
    """Create a new contract"""
    try:
        # Validate that unit is not occupied
        unit = await db.get_document("units", contract_data.unit_id)
        if not unit:
            raise handle_not_found_error("Unit", contract_data.unit_id)
        
        if unit.get("status") == "occupied":
            raise UnitOccupiedException(contract_data.unit_id)
        
        # Validate that tenant is not already assigned
        existing_contract = await db.get_contract_by_tenant(contract_data.tenant_id)
        if existing_contract:
            raise TenantAlreadyAssignedException(contract_data.tenant_id)
        
        # Validate tenant exists
        tenant = await db.get_document("tenants", contract_data.tenant_id)
        if not tenant:
            raise handle_not_found_error("Tenant", contract_data.tenant_id)
        
        # Generate contract ID
        contract_id = f"L-{contract_data.unit_id.split('-')[1]}-{datetime.now().year}"
        
        contract_dict = contract_data.dict()
        contract_dict["contract_id"] = contract_id
        
        document_id = await db.create_document(COLLECTION_CONTRACTS, contract_dict)
        
        # Update unit status to occupied
        await db.update_document("units", contract_data.unit_id, {"status": "occupied", "tenant_id": contract_data.tenant_id})
        
        return SuccessResponse(
            message="Contract created successfully",
            data={"contract_id": contract_id, "document_id": document_id}
        )
    except (UnitOccupiedException, TenantAlreadyAssignedException):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating contract: {e}")
        raise handle_database_error(e, "creating contract")

@router.put("/{contract_id}", response_model=SuccessResponse)
async def update_contract(
    contract_id: str,
    contract_data: ContractUpdate,
    db: DatabaseManager = Depends(get_database)
):
    """Update an existing contract"""
    try:
        # Check if contract exists
        existing_contract = await db.get_document(COLLECTION_CONTRACTS, contract_id)
        if not existing_contract:
            raise handle_not_found_error("Contract", contract_id)
        
        # Check if contract is expired
        if existing_contract.get("status") == "expired":
            raise ContractExpiredException(contract_id)
        
        # Update contract
        update_data = contract_data.dict(exclude_unset=True)
        success = await db.update_document(COLLECTION_CONTRACTS, contract_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="No changes were made to the contract"
            )
        
        return SuccessResponse(
            message="Contract updated successfully",
            data={"contract_id": contract_id}
        )
    except (ContractExpiredException):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update expired contract {contract_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contract {contract_id}: {e}")
        raise handle_database_error(e, f"updating contract {contract_id}")

@router.delete("/{contract_id}", response_model=SuccessResponse)
async def delete_contract(
    contract_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Delete a contract"""
    try:
        # Check if contract exists
        existing_contract = await db.get_document(COLLECTION_CONTRACTS, contract_id)
        if not existing_contract:
            raise handle_not_found_error("Contract", contract_id)
        
        # Update unit status to vacant
        unit_id = existing_contract.get("unit_id")
        if unit_id:
            await db.update_document("units", unit_id, {"status": "vacant", "tenant_id": None})
        
        # Delete contract
        success = await db.delete_document(COLLECTION_CONTRACTS, contract_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to delete contract"
            )
        
        return SuccessResponse(
            message="Contract deleted successfully",
            data={"contract_id": contract_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contract {contract_id}: {e}")
        raise handle_database_error(e, f"deleting contract {contract_id}")

@router.get("/tenant/{tenant_id}", response_model=Contract)
async def get_contract_by_tenant(
    tenant_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get contract for a specific tenant"""
    try:
        contract = await db.get_contract_by_tenant(tenant_id)
        if not contract:
            raise handle_not_found_error("Contract", f"for tenant {tenant_id}")
        return contract
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contract for tenant {tenant_id}: {e}")
        raise handle_database_error(e, f"retrieving contract for tenant {tenant_id}")

@router.post("/{contract_id}/terminate", response_model=SuccessResponse)
async def terminate_contract(
    contract_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Terminate a contract"""
    try:
        # Check if contract exists
        existing_contract = await db.get_document(COLLECTION_CONTRACTS, contract_id)
        if not existing_contract:
            raise handle_not_found_error("Contract", contract_id)
        
        # Update contract status to terminated
        success = await db.update_document(COLLECTION_CONTRACTS, contract_id, {"status": "terminated"})
        
        # Update unit status to vacant
        unit_id = existing_contract.get("unit_id")
        if unit_id:
            await db.update_document("units", unit_id, {"status": "vacant", "tenant_id": None})
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to terminate contract"
            )
        
        return SuccessResponse(
            message="Contract terminated successfully",
            data={"contract_id": contract_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error terminating contract {contract_id}: {e}")
        raise handle_database_error(e, f"terminating contract {contract_id}")

@router.get("/expiring/", response_model=List[Contract])
async def get_expiring_contracts(
    days: int = Query(30, ge=1, le=365, description="Number of days ahead to check"),
    db: DatabaseManager = Depends(get_database)
):
    """Get contracts expiring within specified days"""
    try:
        from datetime import datetime, timedelta
        
        # Calculate the date range
        today = datetime.now().date()
        future_date = (today + timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Get contracts expiring within the range
        contracts = await db.get_documents(
            COLLECTION_CONTRACTS, 
            {
                "end_date": {"$lte": future_date},
                "status": "active"
            }
        )
        
        return contracts
    except Exception as e:
        logger.error(f"Error getting expiring contracts: {e}")
        raise handle_database_error(e, "retrieving expiring contracts")
