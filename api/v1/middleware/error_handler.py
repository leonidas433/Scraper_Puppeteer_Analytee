"""Global error handling middleware"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import traceback

logger = logging.getLogger(__name__)


async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions globally"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "status_code": 500,
            "message": "Internal server error",
            "data": None,
            "errors": [str(exc)] if not isinstance(exc, Exception) else None
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"][1:])
        errors.append(f"{field}: {error['msg']}")
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "status_code": 400,
            "message": "Validation error",
            "data": None,
            "errors": errors
        }
    )


async def not_found_handler(request: Request, exc: Exception):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "success": False,
            "status_code": 404,
            "message": "Resource not found",
            "data": None,
            "errors": [str(exc)]
        }
    )
