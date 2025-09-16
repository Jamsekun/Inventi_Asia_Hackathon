from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from ..database import DatabaseManager, get_database
from ..models import Expense, ExpenseCreate, ExpenseUpdate, SuccessResponse, PaginatedResponse
from ..exceptions import handle_database_error, handle_not_found_error
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/expenses", tags=["Expenses"])

# Collection name constants
COLLECTION_EXPENSES = "Expenses"

@router.get("/", response_model=PaginatedResponse)
async def get_expenses(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    category: Optional[str] = Query(None, description="Filter by expense category"),
    start_date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$', description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$', description="End date filter (YYYY-MM-DD)"),
    db: DatabaseManager = Depends(get_database)
):
    """Get all expenses with optional filtering and pagination"""
    try:
        filter_dict = {}
        if category:
            filter_dict["category"] = category
        
        if start_date and end_date:
            filter_dict["date"] = {"$gte": start_date, "$lte": end_date}
        elif start_date:
            filter_dict["date"] = {"$gte": start_date}
        elif end_date:
            filter_dict["date"] = {"$lte": end_date}
        
        expenses = await db.get_documents(COLLECTION_EXPENSES, filter_dict, skip=skip, limit=limit, sort_field="date", sort_order=-1)
        total = await db.count_documents(COLLECTION_EXPENSES, filter_dict)
        
        return PaginatedResponse(
            items=expenses,
            total=total,
            page=skip // limit + 1,
            size=limit,
            has_next=skip + limit < total,
            has_prev=skip > 0
        )
    except Exception as e:
        logger.error(f"Error getting expenses: {e}")
        raise handle_database_error(e, "retrieving expenses")

@router.get("/{expense_id}", response_model=Expense)
async def get_expense(
    expense_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Get a specific expense by ID"""
    try:
        expense = await db.get_document(COLLECTION_EXPENSES, expense_id)
        if not expense:
            raise handle_not_found_error("Expense", expense_id)
        return expense
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expense {expense_id}: {e}")
        raise handle_database_error(e, f"retrieving expense {expense_id}")

@router.post("/", response_model=SuccessResponse)
async def create_expense(
    expense_data: ExpenseCreate,
    db: DatabaseManager = Depends(get_database)
):
    """Create a new expense"""
    try:
        # Generate expense ID
        expense_id = f"E-{expense_data.date.replace('-', '-')}-{len(await db.get_documents('expenses')) + 1:02d}"
        
        expense_dict = expense_data.dict()
        expense_dict["expense_id"] = expense_id
        
        document_id = await db.create_document(COLLECTION_EXPENSES, expense_dict)
        
        return SuccessResponse(
            message="Expense created successfully",
            data={"expense_id": expense_id, "document_id": document_id}
        )
    except Exception as e:
        logger.error(f"Error creating expense: {e}")
        raise handle_database_error(e, "creating expense")

@router.put("/{expense_id}", response_model=SuccessResponse)
async def update_expense(
    expense_id: str,
    expense_data: ExpenseUpdate,
    db: DatabaseManager = Depends(get_database)
):
    """Update an existing expense"""
    try:
        # Check if expense exists
        existing_expense = await db.get_document(COLLECTION_EXPENSES, expense_id)
        if not existing_expense:
            raise handle_not_found_error("Expense", expense_id)
        
        # Update expense
        update_data = expense_data.dict(exclude_unset=True)
        success = await db.update_document(COLLECTION_EXPENSES, expense_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="No changes were made to the expense"
            )
        
        return SuccessResponse(
            message="Expense updated successfully",
            data={"expense_id": expense_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating expense {expense_id}: {e}")
        raise handle_database_error(e, f"updating expense {expense_id}")

@router.delete("/{expense_id}", response_model=SuccessResponse)
async def delete_expense(
    expense_id: str,
    db: DatabaseManager = Depends(get_database)
):
    """Delete an expense"""
    try:
        # Check if expense exists
        existing_expense = await db.get_document(COLLECTION_EXPENSES, expense_id)
        if not existing_expense:
            raise handle_not_found_error("Expense", expense_id)
        
        # Delete expense
        success = await db.delete_document(COLLECTION_EXPENSES, expense_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to delete expense"
            )
        
        return SuccessResponse(
            message="Expense deleted successfully",
            data={"expense_id": expense_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting expense {expense_id}: {e}")
        raise handle_database_error(e, f"deleting expense {expense_id}")

@router.get("/categories/", response_model=List[str])
async def get_expense_categories(
    db: DatabaseManager = Depends(get_database)
):
    """Get all unique expense categories"""
    try:
        pipeline = [
            {"$group": {"_id": "$category"}},
            {"$sort": {"_id": 1}},
            {"$project": {"_id": 0, "category": "$_id"}}
        ]
        
        if db.db is None:
            raise Exception("Database not initialized. Call connect() first.")
        
        categories = []
        async for doc in db.db[COLLECTION_EXPENSES].aggregate(pipeline):
            categories.append(doc["category"])
        
        return categories
    except Exception as e:
        logger.error(f"Error getting expense categories: {e}")
        raise handle_database_error(e, "retrieving expense categories")

@router.get("/summary/by-category", response_model=dict)
async def get_expenses_by_category(
    start_date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$', description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$', description="End date filter (YYYY-MM-DD)"),
    db: DatabaseManager = Depends(get_database)
):
    """Get expense summary grouped by category"""
    try:
        match_stage = {}
        if start_date and end_date:
            match_stage["date"] = {"$gte": start_date, "$lte": end_date}
        elif start_date:
            match_stage["date"] = {"$gte": start_date}
        elif end_date:
            match_stage["date"] = {"$lte": end_date}
        
        pipeline = [
            {"$match": match_stage},
            {"$group": {
                "_id": "$category",
                "total_amount": {"$sum": "$amount"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"total_amount": -1}},
            {"$project": {
                "_id": 0,
                "category": "$_id",
                "total_amount": 1,
                "count": 1
            }}
        ]
        
        if db.db is None:
            raise Exception("Database not initialized. Call connect() first.")
        
        summary = []
        async for doc in db.db[COLLECTION_EXPENSES].aggregate(pipeline):
            summary.append(doc)
        
        return {"categories": summary}
    except Exception as e:
        logger.error(f"Error getting expense summary by category: {e}")
        raise handle_database_error(e, "retrieving expense summary by category")
