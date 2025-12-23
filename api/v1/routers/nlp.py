"""NLP Service API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from api.dependencies import get_nlp_service
from database.service.analytics import NLPService
from api.v1.schemas.common_schemas import ApiResponse, BatchOperationResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nlp", tags=["nlp"])


@router.post("/analyze-sentiment", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def analyze_sentiment(
    place_id: int,
    limit: int = Query(50, ge=1, le=1000),
    nlp_service: NLPService = Depends(get_nlp_service)
) -> ApiResponse:
    """
    Analyze sentiment for a place
    
    Args:
        place_id: The place ID to analyze
        limit: Number of recent reviews to analyze (default: 50)
    
    Returns:
        ApiResponse: Sentiment analysis results
    """
    try:
        result = nlp_service.analyze_sentiment(place_id, limit)
        return ApiResponse(
            success=True,
            status_code=200,
            message="Sentiment analysis completed",
            data=result
        )
    except ValueError as e:
        logger.warning(f"Sentiment analysis validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {str(e)}")


@router.get("/sentiment-trend/{place_id}", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def get_sentiment_trend(
    place_id: int,
    days: int = Query(30, ge=1, le=365),
    nlp_service: NLPService = Depends(get_nlp_service)
) -> ApiResponse:
    """
    Get sentiment trend for a place over time
    
    Args:
        place_id: The place ID
        days: Number of days to analyze (default: 30)
    
    Returns:
        ApiResponse: Sentiment trend data
    """
    try:
        result = nlp_service.get_sentiment_trend(place_id, days)
        return ApiResponse(
            success=True,
            status_code=200,
            message="Sentiment trend retrieved",
            data=result
        )
    except ValueError as e:
        logger.warning(f"Sentiment trend validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Sentiment trend failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sentiment trend failed: {str(e)}")


@router.post("/batch-analyze", response_model=BatchOperationResponse, status_code=status.HTTP_200_OK)
async def batch_analyze(
    place_ids: List[int],
    limit: int = Query(50, ge=1, le=1000),
    nlp_service: NLPService = Depends(get_nlp_service)
) -> BatchOperationResponse:
    """
    Batch analyze sentiment for multiple places
    
    Args:
        place_ids: List of place IDs to analyze
        limit: Number of recent reviews per place (default: 50)
    
    Returns:
        BatchOperationResponse: Results for all places
    """
    try:
        results = nlp_service.batch_analyze_places(place_ids, limit)
        
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
        logger.warning(f"Batch analysis validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Batch analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")
