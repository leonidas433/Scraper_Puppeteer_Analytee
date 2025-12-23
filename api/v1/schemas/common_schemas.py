"""Common schemas for API responses"""
from typing import Any, Optional, List
from pydantic import BaseModel
from enum import Enum


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApiResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool
    status_code: int
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "status_code": 200,
                "message": "Operation successful",
                "data": {},
                "errors": None
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    database: str
    redis: str
    services: dict


class BatchOperationResponse(BaseModel):
    """Batch operation response"""
    total_items: int
    processed: int
    failed: int
    success_rate: float
    results: List[dict]
    errors: Optional[List[dict]] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
