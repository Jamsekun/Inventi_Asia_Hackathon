from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

# Base Models
class StatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    RESOLVED = "resolved"
    PAID = "paid"
    UNPAID = "unpaid"
    DUE = "due"
    OCCUPIED = "occupied"
    VACANT = "vacant"

# 1. Amenities
class Amenity(BaseModel):
    amenity_id: str = Field(..., description="Unique identifier for the amenity")
    name: str = Field(..., description="Name of the amenity")
    description: str = Field(..., description="Description of the amenity")
    availability: bool = Field(..., description="Whether the amenity is available")
    assigned_units: List[str] = Field(..., description="List of unit IDs that can use this amenity")

class AmenityCreate(BaseModel):
    name: str
    description: str
    availability: bool = True
    assigned_units: List[str] = []

class AmenityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    availability: Optional[bool] = None
    assigned_units: Optional[List[str]] = None

# 2. Contracts
class Contract(BaseModel):
    contract_id: str = Field(..., description="Unique identifier for the contract")
    tenant_id: str = Field(..., description="ID of the tenant")
    unit_id: str = Field(..., description="ID of the unit")
    monthly_rent: float = Field(..., description="Monthly rent amount")
    deposit: float = Field(..., description="Deposit amount")
    start_date: str = Field(..., description="Contract start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Contract end date (YYYY-MM-DD)")
    status: StatusEnum = Field(..., description="Contract status")

class ContractCreate(BaseModel):
    tenant_id: str
    unit_id: str
    monthly_rent: float = Field(..., gt=0, description="Monthly rent must be positive")
    deposit: float = Field(..., gt=0, description="Deposit must be positive")
    start_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Date in YYYY-MM-DD format")
    end_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Date in YYYY-MM-DD format")
    status: StatusEnum = StatusEnum.ACTIVE

class ContractUpdate(BaseModel):
    monthly_rent: Optional[float] = Field(None, gt=0)
    deposit: Optional[float] = Field(None, gt=0)
    start_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    end_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    status: Optional[StatusEnum] = None

# 3. ElecBill
class ElecBill(BaseModel):
    bill_id: str = Field(..., description="Unique identifier for the electricity bill")
    unit_id: str = Field(..., description="ID of the unit")
    amount: float = Field(..., description="Bill amount")
    due_date: str = Field(..., description="Due date (YYYY-MM-DD)")
    status: StatusEnum = Field(..., description="Payment status")

class ElecBillCreate(BaseModel):
    unit_id: str
    amount: float = Field(..., gt=0, description="Amount must be positive")
    due_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Date in YYYY-MM-DD format")
    status: StatusEnum = StatusEnum.UNPAID

class ElecBillUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    due_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    status: Optional[StatusEnum] = None

# 4. Expenses
class Expense(BaseModel):
    expense_id: str = Field(..., description="Unique identifier for the expense")
    category: str = Field(..., description="Expense category")
    amount: float = Field(..., description="Expense amount")
    date: str = Field(..., description="Expense date (YYYY-MM-DD)")
    description: str = Field(..., description="Expense description")

class ExpenseCreate(BaseModel):
    category: str
    amount: float = Field(..., gt=0, description="Amount must be positive")
    date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Date in YYYY-MM-DD format")
    description: str

class ExpenseUpdate(BaseModel):
    category: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    description: Optional[str] = None

# 5. Maintenance
class Maintenance(BaseModel):
    request_id: str = Field(..., description="Unique identifier for the maintenance request")
    unit_id: str = Field(..., description="ID of the unit")
    issue: str = Field(..., description="Description of the issue")
    status: StatusEnum = Field(..., description="Request status")
    reported_date: str = Field(..., description="Date when issue was reported (YYYY-MM-DD)")
    resolved_date: Optional[str] = Field(None, description="Date when issue was resolved (YYYY-MM-DD)")

class MaintenanceCreate(BaseModel):
    unit_id: str
    issue: str
    status: StatusEnum = StatusEnum.PENDING
    reported_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Date in YYYY-MM-DD format")
    resolved_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')

class MaintenanceUpdate(BaseModel):
    issue: Optional[str] = None
    status: Optional[StatusEnum] = None
    reported_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    resolved_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')

# 6. Rent
class Rent(BaseModel):
    rent_id: str = Field(..., description="Unique identifier for the rent record")
    unit_id: str = Field(..., description="ID of the unit")
    tenant_id: str = Field(..., description="ID of the tenant")
    amount: float = Field(..., description="Rent amount")
    month: str = Field(..., description="Rent month (YYYY-MM)")
    status: StatusEnum = Field(..., description="Payment status")
    payment_date: Optional[str] = Field(None, description="Payment date (YYYY-MM-DD)")

class RentCreate(BaseModel):
    unit_id: str
    tenant_id: str
    amount: float = Field(..., gt=0, description="Amount must be positive")
    month: str = Field(..., pattern=r'^\d{4}-\d{2}$', description="Month in YYYY-MM format")
    status: StatusEnum = StatusEnum.UNPAID
    payment_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')

class RentUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    month: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}$')
    status: Optional[StatusEnum] = None
    payment_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')

# 7. Staff
class Staff(BaseModel):
    staff_id: str = Field(..., description="Unique identifier for the staff member")
    name: str = Field(..., description="Staff member name")
    role: str = Field(..., description="Staff role/position")
    contact: str = Field(..., description="Contact information")
    assigned_requests: List[str] = Field(..., description="List of assigned maintenance request IDs")

class StaffCreate(BaseModel):
    name: str
    role: str
    contact: str
    assigned_requests: List[str] = []

class StaffUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    contact: Optional[str] = None
    assigned_requests: Optional[List[str]] = None

# 8. Tenants
class Tenant(BaseModel):
    tenant_id: str = Field(..., description="Unique identifier for the tenant")
    name: str = Field(..., description="Tenant name")
    contact: str = Field(..., description="Contact information")
    email: str = Field(..., description="Email address")
    unit_id: str = Field(..., description="ID of the assigned unit")

class TenantCreate(BaseModel):
    name: str
    contact: str
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', description="Valid email format")
    unit_id: str

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    contact: Optional[str] = None
    email: Optional[str] = Field(None, pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    unit_id: Optional[str] = None

# 9. Units
class Unit(BaseModel):
    unit_id: str = Field(..., description="Unique identifier for the unit")
    floor: int = Field(..., description="Floor number", ge=1)
    number: str = Field(..., description="Unit number")
    status: StatusEnum = Field(..., description="Unit status (occupied/vacant)")
    tenant_id: Optional[str] = Field(None, description="ID of the current tenant")

class UnitCreate(BaseModel):
    floor: int = Field(..., ge=1, description="Floor must be at least 1")
    number: str
    status: StatusEnum = StatusEnum.VACANT
    tenant_id: Optional[str] = None

class UnitUpdate(BaseModel):
    floor: Optional[int] = Field(None, ge=1)
    number: Optional[str] = None
    status: Optional[StatusEnum] = None
    tenant_id: Optional[str] = None

# 10. WaterBill
class WaterBill(BaseModel):
    bill_id: str = Field(..., description="Unique identifier for the water bill")
    unit_id: str = Field(..., description="ID of the unit")
    amount: float = Field(..., description="Bill amount")
    due_date: str = Field(..., description="Due date (YYYY-MM-DD)")
    status: StatusEnum = Field(..., description="Payment status")

class WaterBillCreate(BaseModel):
    unit_id: str
    amount: float = Field(..., gt=0, description="Amount must be positive")
    due_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Date in YYYY-MM-DD format")
    status: StatusEnum = StatusEnum.UNPAID

class WaterBillUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    due_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    status: Optional[StatusEnum] = None

# RAG System Models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    collection_focus: Optional[str] = Field(None, description="Specific collection to focus on")

class RAGResponse(BaseModel):
    intent: str = Field(..., description="Detected intent")
    response: str = Field(..., description="Generated response")
    relevant_data: Optional[dict] = Field(None, description="Retrieved relevant data")

# Response Models
class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[dict] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[str] = None

# Pagination Models
class PaginatedResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    size: int
    has_next: bool
    has_prev: bool

# Summary Models
class BillSummary(BaseModel):
    period: str
    total_amount: float
    due_items: int
    paid_items: int
    unpaid_items: int

class PropertySummary(BaseModel):
    total_units: int
    occupied_units: int
    vacant_units: int
    total_tenants: int
    total_staff: int
    pending_maintenance: int
    monthly_income: float
    monthly_expenses: float