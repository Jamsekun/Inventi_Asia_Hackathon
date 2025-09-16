from fastapi import HTTPException, status
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class PropertyManagementException(Exception):
    """Base exception for property management system"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class DatabaseException(PropertyManagementException):
    """Database-related exceptions"""
    pass

class ValidationException(PropertyManagementException):
    """Data validation exceptions"""
    pass

class NotFoundException(PropertyManagementException):
    """Resource not found exceptions"""
    pass

class ConflictException(PropertyManagementException):
    """Resource conflict exceptions"""
    pass
    
class AuthenticationException(PropertyManagementException):
    """Authentication-related exceptions"""
    pass

class AuthorizationException(PropertyManagementException):
    """Authorization-related exceptions"""
    pass

class ExternalServiceException(PropertyManagementException):
    """External service exceptions"""
    pass

# HTTP Exception handlers
def create_http_exception(
    status_code: int,
    message: str,
    details: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None
) -> HTTPException:
    """Create a standardized HTTP exception"""
    return HTTPException(
        status_code=status_code,
        detail={
            "error": message,
            "details": details,
            "success": False
        },
        headers=headers
    )

def handle_database_error(error: Exception, operation: str) -> HTTPException:
    """Handle database errors and convert to appropriate HTTP exceptions"""
    logger.error(f"Database error during {operation}: {error}")
    
    if "duplicate key" in str(error).lower():
        return create_http_exception(
            status_code=status.HTTP_409_CONFLICT,
            message=f"Resource already exists",
            details=f"A record with this identifier already exists"
        )
    elif "not found" in str(error).lower():
        return create_http_exception(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Resource not found",
            details=f"The requested resource could not be found"
        )
    elif "validation" in str(error).lower():
        return create_http_exception(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=f"Validation error",
            details=str(error)
        )
    else:
        return create_http_exception(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"Database operation failed",
            details=f"An error occurred while {operation}"
        )

def handle_validation_error(error: Exception, field: Optional[str] = None) -> HTTPException:
    """Handle validation errors and convert to appropriate HTTP exceptions"""
    logger.error(f"Validation error: {error}")
    
    if field:
        message = f"Validation error in field '{field}'"
    else:
        message = "Validation error"
    
    return create_http_exception(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message=message,
        details=str(error)
    )

def handle_not_found_error(resource_type: str, resource_id: str) -> HTTPException:
    """Handle resource not found errors"""
    return create_http_exception(
        status_code=status.HTTP_404_NOT_FOUND,
        message=f"{resource_type} not found",
        details=f"No {resource_type.lower()} found with ID: {resource_id}"
    )

def handle_conflict_error(resource_type: str, conflict_reason: str) -> HTTPException:
    """Handle resource conflict errors"""
    return create_http_exception(
        status_code=status.HTTP_409_CONFLICT,
        message=f"{resource_type} conflict",
        details=conflict_reason
    )

def handle_authentication_error(reason: str = "Authentication failed") -> HTTPException:
    """Handle authentication errors"""
    return create_http_exception(
        status_code=status.HTTP_401_UNAUTHORIZED,
        message="Authentication required",
        details=reason,
        headers={"WWW-Authenticate": "Bearer"}
    )

def handle_authorization_error(reason: str = "Insufficient permissions") -> HTTPException:
    """Handle authorization errors"""
    return create_http_exception(
        status_code=status.HTTP_403_FORBIDDEN,
        message="Access denied",
        details=reason
    )

def handle_external_service_error(service_name: str, error: Exception) -> HTTPException:
    """Handle external service errors"""
    logger.error(f"External service error ({service_name}): {error}")
    
    return create_http_exception(
        status_code=status.HTTP_502_BAD_GATEWAY,
        message=f"External service unavailable",
        details=f"Error communicating with {service_name}: {str(error)}"
    )

# Specific business logic exceptions
class UnitOccupiedException(ConflictException):
    """Raised when trying to assign a tenant to an occupied unit"""
    def __init__(self, unit_id: str):
        super().__init__(
            message=f"Unit {unit_id} is already occupied",
            details={"unit_id": unit_id, "conflict_type": "unit_occupied"}
        )

class TenantAlreadyAssignedException(ConflictException):
    """Raised when trying to assign a tenant who already has a unit"""
    def __init__(self, tenant_id: str):
        super().__init__(
            message=f"Tenant {tenant_id} is already assigned to a unit",
            details={"tenant_id": tenant_id, "conflict_type": "tenant_assigned"}
        )

class ContractExpiredException(ValidationException):
    """Raised when trying to perform operations on an expired contract"""
    def __init__(self, contract_id: str):
        super().__init__(
            message=f"Contract {contract_id} has expired",
            details={"contract_id": contract_id, "error_type": "contract_expired"}
        )

class InsufficientFundsException(ValidationException):
    """Raised when trying to process payment with insufficient funds"""
    def __init__(self, required_amount: float, available_amount: float):
        super().__init__(
            message="Insufficient funds for payment",
            details={
                "required_amount": required_amount,
                "available_amount": available_amount,
                "deficit": required_amount - available_amount
            }
        )

class MaintenanceAlreadyResolvedException(ConflictException):
    """Raised when trying to resolve an already resolved maintenance request"""
    def __init__(self, request_id: str):
        super().__init__(
            message=f"Maintenance request {request_id} is already resolved",
            details={"request_id": request_id, "conflict_type": "already_resolved"}
        )

class InvalidDateRangeException(ValidationException):
    """Raised when date range is invalid"""
    def __init__(self, start_date: str, end_date: str):
        super().__init__(
            message="Invalid date range",
            details={
                "start_date": start_date,
                "end_date": end_date,
                "error_type": "invalid_date_range"
            }
        )

class AmenityNotAvailableException(ValidationException):
    """Raised when trying to use an unavailable amenity"""
    def __init__(self, amenity_id: str):
        super().__init__(
            message=f"Amenity {amenity_id} is not available",
            details={"amenity_id": amenity_id, "error_type": "amenity_unavailable"}
        )

class UnitNotEligibleForAmenityException(ValidationException):
    """Raised when unit is not eligible for an amenity"""
    def __init__(self, unit_id: str, amenity_id: str):
        super().__init__(
            message=f"Unit {unit_id} is not eligible for amenity {amenity_id}",
            details={
                "unit_id": unit_id,
                "amenity_id": amenity_id,
                "error_type": "unit_not_eligible"
            }
        )

# RAG System exceptions
class RAGSystemException(PropertyManagementException):
    """RAG system related exceptions"""
    pass

class IntentDetectionException(RAGSystemException):
    """Intent detection exceptions"""
    pass

class DataRetrievalException(RAGSystemException):
    """Data retrieval exceptions"""
    pass

class ResponseGenerationException(RAGSystemException):
    """Response generation exceptions"""
    pass

# Exception handler functions for specific scenarios
def validate_required_fields(data: dict, required_fields: list) -> None:
    """Validate that all required fields are present"""
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    if missing_fields:
        raise ValidationException(
            message="Missing required fields",
            details={"missing_fields": missing_fields}
        )

def validate_positive_amount(amount: float, field_name: str = "amount") -> None:
    """Validate that amount is positive"""
    if amount <= 0:
        raise ValidationException(
            message=f"{field_name} must be positive",
            details={"field": field_name, "value": amount}
        )

def validate_date_format(date_string: str, field_name: str = "date") -> None:
    """Validate date format (YYYY-MM-DD)"""
    import re
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_string):
        raise ValidationException(
            message=f"{field_name} must be in YYYY-MM-DD format",
            details={"field": field_name, "value": date_string}
        )

def validate_month_format(month_string: str, field_name: str = "month") -> None:
    """Validate month format (YYYY-MM)"""
    import re
    if not re.match(r'^\d{4}-\d{2}$', month_string):
        raise ValidationException(
            message=f"{field_name} must be in YYYY-MM format",
            details={"field": field_name, "value": month_string}
        )

def validate_email_format(email: str) -> None:
    """Validate email format"""
    import re
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValidationException(
            message="Invalid email format",
            details={"field": "email", "value": email}
        )

def validate_unit_id_format(unit_id: str) -> None:
    """Validate unit ID format (U-XXX)"""
    import re
    if not re.match(r'^U-\d+$', unit_id):
        raise ValidationException(
            message="Unit ID must be in format U-XXX",
            details={"field": "unit_id", "value": unit_id}
        )

def validate_tenant_id_format(tenant_id: str) -> None:
    """Validate tenant ID format (T-XXX)"""
    import re
    if not re.match(r'^T-\d+$', tenant_id):
        raise ValidationException(
            message="Tenant ID must be in format T-XXX",
            details={"field": "tenant_id", "value": tenant_id}
        )

def validate_contract_id_format(contract_id: str) -> None:
    """Validate contract ID format (L-XXX-YYYY)"""
    import re
    if not re.match(r'^L-\d+-\d{4}$', contract_id):
        raise ValidationException(
            message="Contract ID must be in format L-XXX-YYYY",
            details={"field": "contract_id", "value": contract_id}
        )
