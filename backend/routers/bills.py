from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from ..database import DatabaseManager, get_database
from ..models import (
    ElecBill, ElecBillCreate, ElecBillUpdate,
    WaterBill, WaterBillCreate, WaterBillUpdate,
    BillSummary, SuccessResponse, PaginatedResponse
)
from ..exceptions import handle_database_error, handle_not_found_error
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bills", tags=["bills"])

# Collection name constants
COLLECTION_ELEC_BILL = "ElecBill"
COLLECTION_WATER_BILL = "WaterBill"

@router.on_event("startup")
async def validate_collections():
    """Validate that required collections exist on startup"""
    try:
        db = await get_database()
        collections = await db.db.list_collection_names()
        required_collections = [COLLECTION_ELEC_BILL, COLLECTION_WATER_BILL]
        for collection in required_collections:
            if collection not in collections:
                logger.error(f"Required collection '{collection}' not found in database")
                raise ValueError(f"Collection '{collection}' does not exist in database")
            logger.info(f"Collection '{collection}' found in database")
    except Exception as e:
        logger.error(f"Failed to validate collections on startup: {e}")
        raise

# Electric Bills Routes
@router.get("/electric/", response_model=PaginatedResponse)
async def get_electric_bills(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    unit_id: Optional[str] = Query(None, description="Filter by unit ID"),
    status: Optional[str] = Query(None, description="Filter by payment status"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all electric bills with optional filtering and pagination"""
    try:
        logger.info(f"Querying collection '{COLLECTION_ELEC_BILL}' with filters: unit_id={unit_id}, status={status}")
        filter_dict = {}
        if unit_id:
            filter_dict["unit_id"] = unit_id
        if status:
            filter_dict["status"] = status
        
        bills = await db.get_documents(COLLECTION_ELEC_BILL, filter_dict, skip=skip, limit=limit)
        total = await db.count_documents(COLLECTION_ELEC_BILL, filter_dict)
        
        logger.info(f"Retrieved {len(bills)} electric bills from '{COLLECTION_ELEC_BILL}' (total: {total})")
        return PaginatedResponse(
            items=bills,
            total=total,
            page=skip // limit + 1,
            size=limit,
            has_next=skip + limit < total,
            has_prev=skip > 0
        )
    except Exception as e:
        logger.error(f"Error getting electric bills from '{COLLECTION_ELEC_BILL}': {e}")
        raise handle_database_error(e, "retrieving electric bills")

@router.get("/electric/{bill_id}", response_model=ElecBill)
async def get_electric_bill(
    bill_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get a specific electric bill by ID"""
    try:
        logger.info(f"Querying collection '{COLLECTION_ELEC_BILL}' for bill_id={bill_id}")
        bill = await db.get_document(COLLECTION_ELEC_BILL, bill_id)
        if not bill:
            logger.warning(f"No electric bill found in '{COLLECTION_ELEC_BILL}' for bill_id={bill_id}")
            raise handle_not_found_error("Electric Bill", bill_id)
        logger.info(f"Retrieved electric bill {bill_id} from '{COLLECTION_ELEC_BILL}'")
        return bill
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting electric bill {bill_id} from '{COLLECTION_ELEC_BILL}': {e}")
        raise handle_database_error(e, f"retrieving electric bill {bill_id}")

@router.post("/electric/", response_model=SuccessResponse)
async def create_electric_bill(
    bill_data: ElecBillCreate,
    db: DatabaseManager = Depends(get_database)
):
    """Create a new electric bill"""
    try:
        logger.info(f"Creating new electric bill in '{COLLECTION_ELEC_BILL}' for unit_id={bill_data.unit_id}")
        # Generate bill ID
        bill_id = f"EB-{bill_data.due_date.replace('-', '-')}-{bill_data.unit_id.split('-')[1]}"
        
        bill_dict = bill_data.dict()
        bill_dict["bill_id"] = bill_id
        
        document_id = await db.create_document(COLLECTION_ELEC_BILL, bill_dict)
        
        logger.info(f"Created electric bill {bill_id} in '{COLLECTION_ELEC_BILL}' with document_id={document_id}")
        return SuccessResponse(
            message="Electric bill created successfully",
            data={"bill_id": bill_id, "document_id": document_id}
        )
    except Exception as e:
        logger.error(f"Error creating electric bill in '{COLLECTION_ELEC_BILL}': {e}")
        raise handle_database_error(e, "creating electric bill")

@router.put("/electric/{bill_id}", response_model=SuccessResponse)
async def update_electric_bill(
    bill_id: str,
    bill_data: ElecBillUpdate,
    db: DatabaseManager = Depends(get_database)
):
    """Update an existing electric bill"""
    try:
        logger.info(f"Updating electric bill {bill_id} in '{COLLECTION_ELEC_BILL}'")
        # Check if bill exists
        existing_bill = await db.get_document(COLLECTION_ELEC_BILL, bill_id)
        if not existing_bill:
            logger.warning(f"No electric bill found in '{COLLECTION_ELEC_BILL}' for bill_id={bill_id}")
            raise handle_not_found_error("Electric Bill", bill_id)
        
        # Update bill
        update_data = bill_data.dict(exclude_unset=True)
        success = await db.update_document(COLLECTION_ELEC_BILL, bill_id, update_data)
        
        if not success:
            logger.warning(f"No changes made to electric bill {bill_id} in '{COLLECTION_ELEC_BILL}'")
            raise HTTPException(
                status_code=400,
                detail="No changes were made to the electric bill"
            )
        
        logger.info(f"Updated electric bill {bill_id} in '{COLLECTION_ELEC_BILL}'")
        return SuccessResponse(
            message="Electric bill updated successfully",
            data={"bill_id": bill_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating electric bill {bill_id} in '{COLLECTION_ELEC_BILL}': {e}")
        raise handle_database_error(e, f"updating electric bill {bill_id}")

@router.delete("/electric/{bill_id}", response_model=SuccessResponse)
async def delete_electric_bill(
    bill_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Delete an electric bill"""
    try:
        logger.info(f"Deleting electric bill {bill_id} from '{COLLECTION_ELEC_BILL}'")
        # Check if bill exists
        existing_bill = await db.get_document(COLLECTION_ELEC_BILL, bill_id)
        if not existing_bill:
            logger.warning(f"No electric bill found in '{COLLECTION_ELEC_BILL}' for bill_id={bill_id}")
            raise handle_not_found_error("Electric Bill", bill_id)
        
        # Delete bill
        success = await db.delete_document(COLLECTION_ELEC_BILL, bill_id)
        
        if not success:
            logger.warning(f"Failed to delete electric bill {bill_id} from '{COLLECTION_ELEC_BILL}'")
            raise HTTPException(
                status_code=400,
                detail="Failed to delete electric bill"
            )
        
        logger.info(f"Deleted electric bill {bill_id} from '{COLLECTION_ELEC_BILL}'")
        return SuccessResponse(
            message="Electric bill deleted successfully",
            data={"bill_id": bill_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting electric bill {bill_id} from '{COLLECTION_ELEC_BILL}': {e}")
        raise handle_database_error(e, f"deleting electric bill {bill_id}")

# Water Bills Routes
@router.get("/water/", response_model=PaginatedResponse)
async def get_water_bills(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    unit_id: Optional[str] = Query(None, description="Filter by unit ID"),
    status: Optional[str] = Query(None, description="Filter by payment status"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all water bills with optional filtering and pagination"""
    try:
        logger.info(f"Querying collection '{COLLECTION_WATER_BILL}' with filters: unit_id={unit_id}, status={status}")
        filter_dict = {}
        if unit_id:
            filter_dict["unit_id"] = unit_id
        if status:
            filter_dict["status"] = status
        
        bills = await db.get_documents(COLLECTION_WATER_BILL, filter_dict, skip=skip, limit=limit)
        total = await db.count_documents(COLLECTION_WATER_BILL, filter_dict)
        
        logger.info(f"Retrieved {len(bills)} water bills from '{COLLECTION_WATER_BILL}' (total: {total})")
        return PaginatedResponse(
            items=bills,
            total=total,
            page=skip // limit + 1,
            size=limit,
            has_next=skip + limit < total,
            has_prev=skip > 0
        )
    except Exception as e:
        logger.error(f"Error getting water bills from '{COLLECTION_WATER_BILL}': {e}")
        raise handle_database_error(e, "retrieving water bills")

@router.get("/water/{bill_id}", response_model=WaterBill)
async def get_water_bill(
    bill_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get a specific water bill by ID"""
    try:
        logger.info(f"Querying collection '{COLLECTION_WATER_BILL}' for bill_id={bill_id}")
        bill = await db.get_document(COLLECTION_WATER_BILL, bill_id)
        if not bill:
            logger.warning(f"No water bill found in '{COLLECTION_WATER_BILL}' for bill_id={bill_id}")
            raise handle_not_found_error("Water Bill", bill_id)
        logger.info(f"Retrieved water bill {bill_id} from '{COLLECTION_WATER_BILL}'")
        return bill
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting water bill {bill_id} from '{COLLECTION_WATER_BILL}': {e}")
        raise handle_database_error(e, f"retrieving water bill {bill_id}")

@router.post("/water/", response_model=SuccessResponse)
async def create_water_bill(
    bill_data: WaterBillCreate,
    db: DatabaseManager = Depends(get_database)
):
    """Create a new water bill"""
    try:
        logger.info(f"Creating new water bill in '{COLLECTION_WATER_BILL}' for unit_id={bill_data.unit_id}")
        # Generate bill ID
        bill_id = f"WB-{bill_data.due_date.replace('-', '-')}-{bill_data.unit_id.split('-')[1]}"
        
        bill_dict = bill_data.dict()
        bill_dict["bill_id"] = bill_id
        
        document_id = await db.create_document(COLLECTION_WATER_BILL, bill_dict)
        
        logger.info(f"Created water bill {bill_id} in '{COLLECTION_WATER_BILL}' with document_id={document_id}")
        return SuccessResponse(
            message="Water bill created successfully",
            data={"bill_id": bill_id, "document_id": document_id}
        )
    except Exception as e:
        logger.error(f"Error creating water bill in '{COLLECTION_WATER_BILL}': {e}")
        raise handle_database_error(e, "creating water bill")

@router.put("/water/{bill_id}", response_model=SuccessResponse)
async def update_water_bill(
    bill_id: str,
    bill_data: WaterBillUpdate,
    db: DatabaseManager = Depends(get_database)
):
    """Update an existing water bill"""
    try:
        logger.info(f"Updating water bill {bill_id} in '{COLLECTION_WATER_BILL}'")
        # Check if bill exists
        existing_bill = await db.get_document(COLLECTION_WATER_BILL, bill_id)
        if not existing_bill:
            logger.warning(f"No water bill found in '{COLLECTION_WATER_BILL}' for bill_id={bill_id}")
            raise handle_not_found_error("Water Bill", bill_id)
        
        # Update bill
        update_data = bill_data.dict(exclude_unset=True)
        success = await db.update_document(COLLECTION_WATER_BILL, bill_id, update_data)
        
        if not success:
            logger.warning(f"No changes made to water bill {bill_id} in '{COLLECTION_WATER_BILL}'")
            raise HTTPException(
                status_code=400,
                detail="No changes were made to the water bill"
            )
        
        logger.info(f"Updated water bill {bill_id} in '{COLLECTION_WATER_BILL}'")
        return SuccessResponse(
            message="Water bill updated successfully",
            data={"bill_id": bill_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating water bill {bill_id} in '{COLLECTION_WATER_BILL}': {e}")
        raise handle_database_error(e, f"updating water bill {bill_id}")

@router.delete("/water/{bill_id}", response_model=SuccessResponse)
async def delete_water_bill(
    bill_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Delete a water bill"""
    try:
        logger.info(f"Deleting water bill {bill_id} from '{COLLECTION_WATER_BILL}'")
        # Check if bill exists
        existing_bill = await db.get_document(COLLECTION_WATER_BILL, bill_id)
        if not existing_bill:
            logger.warning(f"No water bill found in '{COLLECTION_WATER_BILL}' for bill_id={bill_id}")
            raise handle_not_found_error("Water Bill", bill_id)
        
        # Delete bill
        success = await db.delete_document(COLLECTION_WATER_BILL, bill_id)
        
        if not success:
            logger.warning(f"Failed to delete water bill {bill_id} from '{COLLECTION_WATER_BILL}'")
            raise HTTPException(
                status_code=400,
                detail="Failed to delete water bill"
            )
        
        logger.info(f"Deleted water bill {bill_id} from '{COLLECTION_WATER_BILL}'")
        return SuccessResponse(
            message="Water bill deleted successfully",
            data={"bill_id": bill_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting water bill {bill_id} from '{COLLECTION_WATER_BILL}': {e}")
        raise handle_database_error(e, f"deleting water bill {bill_id}")

# Combined Bills Routes
@router.get("/unit/{unit_id}", response_model=List[dict])
async def get_bills_for_unit(
    unit_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get all bills (electric and water) for a specific unit"""
    try:
        logger.info(f"Querying bills for unit_id={unit_id} from '{COLLECTION_ELEC_BILL}' and '{COLLECTION_WATER_BILL}'")
        bills = await db.get_bills_by_unit(unit_id)
        logger.info(f"Retrieved {len(bills)} bills for unit_id={unit_id}")
        return bills
    except Exception as e:
        logger.error(f"Error getting bills for unit {unit_id} from '{COLLECTION_ELEC_BILL}' and '{COLLECTION_WATER_BILL}': {e}")
        raise handle_database_error(e, f"retrieving bills for unit {unit_id}")

@router.get("/summary/", response_model=BillSummary)
async def get_bills_summary(
    period: Optional[str] = Query(None, description="Period in YYYY-MM format"),
    db: DatabaseManager = Depends(get_database)
):
    """Get summary of bills for a specific period"""
    try:
        logger.info(f"Querying bills summary for period={period} from '{COLLECTION_ELEC_BILL}' and '{COLLECTION_WATER_BILL}'")
        summary = await db.get_bills_summary(period)
        logger.info(f"Retrieved bills summary for period={period}")
        return summary
    except Exception as e:
        logger.error(f"Error getting bills summary from '{COLLECTION_ELEC_BILL}' and '{COLLECTION_WATER_BILL}': {e}")
        raise handle_database_error(e, "retrieving bills summary")

@router.post("/electric/{bill_id}/pay", response_model=SuccessResponse)
async def pay_electric_bill(
    bill_id: str,
    payment_date: str = Query(..., regex=r'^\d{4}-\d{2}-\d{2}$', description="Payment date in YYYY-MM-DD format"),
    db: DatabaseManager = Depends(get_database)
):
    """Mark an electric bill as paid"""
    try:
        logger.info(f"Marking electric bill {bill_id} as paid in '{COLLECTION_ELEC_BILL}'")
        # Check if bill exists
        existing_bill = await db.get_document(COLLECTION_ELEC_BILL, bill_id)
        if not existing_bill:
            logger.warning(f"No electric bill found in '{COLLECTION_ELEC_BILL}' for bill_id={bill_id}")
            raise handle_not_found_error("Electric Bill", bill_id)
        
        # Update bill status to paid
        success = await db.update_document(COLLECTION_ELEC_BILL, bill_id, {
            "status": "paid",
            "payment_date": payment_date
        })
        
        if not success:
            logger.warning(f"Failed to update payment status for electric bill {bill_id} in '{COLLECTION_ELEC_BILL}'")
            raise HTTPException(
                status_code=400,
                detail="Failed to update electric bill payment status"
            )
        
        logger.info(f"Marked electric bill {bill_id} as paid in '{COLLECTION_ELEC_BILL}'")
        return SuccessResponse(
            message="Electric bill marked as paid",
            data={"bill_id": bill_id, "payment_date": payment_date}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error paying electric bill {bill_id} in '{COLLECTION_ELEC_BILL}': {e}")
        raise handle_database_error(e, f"updating electric bill payment status {bill_id}")

@router.post("/water/{bill_id}/pay", response_model=SuccessResponse)
async def pay_water_bill(
    bill_id: str,
    payment_date: str = Query(..., regex=r'^\d{4}-\d{2}-\d{2}$', description="Payment date in YYYY-MM-DD format"),
    db: DatabaseManager = Depends(get_database)
):
    """Mark a water bill as paid"""
    try:
        logger.info(f"Marking water bill {bill_id} as paid in '{COLLECTION_WATER_BILL}'")
        # Check if bill exists
        existing_bill = await db.get_document(COLLECTION_WATER_BILL, bill_id)
        if not existing_bill:
            logger.warning(f"No water bill found in '{COLLECTION_WATER_BILL}' for bill_id={bill_id}")
            raise handle_not_found_error("Water Bill", bill_id)
        
        # Update bill status to paid
        success = await db.update_document(COLLECTION_WATER_BILL, bill_id, {
            "status": "paid",
            "payment_date": payment_date
        })
        
        if not success:
            logger.warning(f"Failed to update payment status for water bill {bill_id} in '{COLLECTION_WATER_BILL}'")
            raise HTTPException(
                status_code=400,
                detail="Failed to update water bill payment status"
            )
        
        logger.info(f"Marked water bill {bill_id} as paid in '{COLLECTION_WATER_BILL}'")
        return SuccessResponse(
            message="Water bill marked as paid",
            data={"bill_id": bill_id, "payment_date": payment_date}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error paying water bill {bill_id} in '{COLLECTION_WATER_BILL}': {e}")
        raise handle_database_error(e, f"updating water bill payment status {bill_id}")