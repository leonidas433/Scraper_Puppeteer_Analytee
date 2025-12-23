"""Correlation Service API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from api.dependencies import get_correlation_service
from database.service.analytics import CorrelationService
from api.v1.schemas.common_schemas import ApiResponse, BatchOperationResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/correlations", tags=["correlations"])


@router.post("/analyze", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def analyze_correlations(
    place_id: int,
    method: str = Query("pearson", regex="^(pearson|spearman)$"),
    min_correlation: float = Query(0.3, ge=0.0, le=1.0),
    correlation_service: CorrelationService = Depends(get_correlation_service)
) -> ApiResponse:
    """
    Analyze correlations between place factors
    
    Args:
        place_id: The place ID to analyze
        method: Correlation method - 'pearson' or 'spearman' (default: pearson)
        min_correlation: Minimum correlation threshold (default: 0.3)
    
    Returns:
        ApiResponse: Correlation analysis results
    """
    try:
        result = correlation_service.analyze_place_correlations(place_id, method, min_correlation)
        return ApiResponse(
            success=True,
            status_code=200,
            message="Correlation analysis completed",
            data=result
        )
    except ValueError as e:
        logger.warning(f"Correlation analysis validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Correlation analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Correlation analysis failed: {str(e)}")


@router.get("/peer-group/{place_id}", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def get_peer_group(
    place_id: int,
    peer_count: int = Query(5, ge=1, le=50),
    correlation_service: CorrelationService = Depends(get_correlation_service)
) -> ApiResponse:
    """
    Get peer group (most similar places) for a place
    
    Args:
        place_id: The place ID
        peer_count: Number of peers to return (default: 5)
    
    Returns:
        ApiResponse: List of peer places with similarity scores
    """
    try:
        result = correlation_service.get_peer_group_correlations(place_id, peer_count)
        return ApiResponse(
            success=True,
            status_code=200,
            message="Peer group retrieved",
            data=result
        )
    except ValueError as e:
        logger.warning(f"Peer group validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Peer group retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Peer group retrieval failed: {str(e)}")


@router.post("/batch", response_model=BatchOperationResponse, status_code=status.HTTP_200_OK)
async def batch_correlations(
    place_ids: List[int],
    correlation_service: CorrelationService = Depends(get_correlation_service)
) -> BatchOperationResponse:
    """
    Batch analyze correlations for multiple places
    
    Args:
        place_ids: List of place IDs to analyze
    
    Returns:
        BatchOperationResponse: Correlation results for all places
    """
    try:
        results = correlation_service.batch_correlations(place_ids)
        
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
        logger.warning(f"Batch correlation validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Batch correlations failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch correlations failed: {str(e)}")
