"""Health check endpoint"""
from fastapi import APIRouter, status
from api.v1.schemas.common_schemas import HealthCheckResponse, ApiResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def health_check() -> ApiResponse:
    """
    Health check endpoint
    
    Returns:
        ApiResponse: System health status
    """
    try:
        return ApiResponse(
            success=True,
            status_code=200,
            message="System is healthy",
            data={
                "status": "operational",
                "services": {
                    "nlp": "active",
                    "prediction": "active",
                    "correlation": "active",
                    "clustering": "active",
                    "pattern_detection": "active"
                }
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return ApiResponse(
            success=False,
            status_code=500,
            message="Health check failed",
            data=None,
            errors=[str(e)]
        )
