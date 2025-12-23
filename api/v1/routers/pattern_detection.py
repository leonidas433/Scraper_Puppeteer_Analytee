"""Pattern Detection Service API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from api.dependencies import get_pattern_service
from database.service.analytics import PatternDetectionService
from api.v1.schemas.common_schemas import ApiResponse, BatchOperationResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.post("/text", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def detect_text_patterns(
    place_id: int,
    min_frequency: int = Query(3, ge=1, le=50),
    pattern_service: PatternDetectionService = Depends(get_pattern_service)
) -> ApiResponse:
    """
    Detect text patterns (keywords and frequencies) in reviews
    
    Args:
        place_id: The place ID to analyze
        min_frequency: Minimum keyword frequency (default: 3)
    
    Returns:
        ApiResponse: Text patterns and keyword frequencies
    """
    try:
        result = pattern_service.detect_text_patterns(place_id, min_frequency)
        return ApiResponse(
            success=True,
            status_code=200,
            message="Text patterns detected",
            data=result
        )
    except ValueError as e:
        logger.warning(f"Text pattern detection validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Text pattern detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Text pattern detection failed: {str(e)}")


@router.post("/temporal", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def detect_temporal_patterns(
    place_id: int,
    window_days: int = Query(7, ge=1, le=90),
    pattern_service: PatternDetectionService = Depends(get_pattern_service)
) -> ApiResponse:
    """
    Detect temporal patterns (peak days/hours) in review data
    
    Args:
        place_id: The place ID to analyze
        window_days: Time window in days (default: 7)
    
    Returns:
        ApiResponse: Temporal patterns (peak days, hours, etc.)
    """
    try:
        result = pattern_service.detect_temporal_patterns(place_id, window_days)
        return ApiResponse(
            success=True,
            status_code=200,
            message="Temporal patterns detected",
            data=result
        )
    except ValueError as e:
        logger.warning(f"Temporal pattern detection validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Temporal pattern detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Temporal pattern detection failed: {str(e)}")


@router.post("/anomalies", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def detect_behavioral_anomalies(
    place_id: int,
    threshold: float = Query(0.8, ge=0.5, le=1.0),
    pattern_service: PatternDetectionService = Depends(get_pattern_service)
) -> ApiResponse:
    """
    Detect behavioral anomalies (rating volatility, review spikes)
    
    Args:
        place_id: The place ID to analyze
        threshold: Anomaly detection threshold (0.5-1.0, default: 0.8)
    
    Returns:
        ApiResponse: Detected behavioral anomalies
    """
    try:
        result = pattern_service.detect_behavioral_anomalies(place_id, threshold)
        return ApiResponse(
            success=True,
            status_code=200,
            message="Behavioral anomalies detected",
            data=result
        )
    except ValueError as e:
        logger.warning(f"Behavioral anomaly detection validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Behavioral anomaly detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Behavioral anomaly detection failed: {str(e)}")


@router.post("/batch", response_model=BatchOperationResponse, status_code=status.HTTP_200_OK)
async def batch_pattern_detection(
    place_ids: List[int],
    pattern_types: Optional[List[str]] = Query(None, description="Pattern types: text, temporal, behavioral"),
    pattern_service: PatternDetectionService = Depends(get_pattern_service)
) -> BatchOperationResponse:
    """
    Batch pattern detection for multiple places
    
    Args:
        place_ids: List of place IDs to analyze
        pattern_types: Optional list of pattern types to detect
    
    Returns:
        BatchOperationResponse: Pattern detection results for all places
    """
    try:
        results = pattern_service.batch_pattern_detection(place_ids, pattern_types)
        
        failed = sum(1 for r in results if not r.get("success", True))
        success = len(results) - failed
        
        return BatchOperationResponse(
            total_items=len(place_ids),
            processed=success,
            failed=failed,
            success_rate=success / len(place_ids) if place_ids else 0,
            results=results
        )
    except ValueError as e:
        logger.warning(f"Batch pattern detection validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Batch pattern detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch pattern detection failed: {str(e)}")
