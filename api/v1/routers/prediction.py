"""Prediction Service API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from api.dependencies import get_prediction_service
from database.service.analytics import PredictionService
from api.v1.schemas.common_schemas import ApiResponse, BatchOperationResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("/forecast", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def forecast_sentiment(
    place_id: int,
    forecast_days: int = Query(7, ge=1, le=90),
    prediction_service: PredictionService = Depends(get_prediction_service)
) -> ApiResponse:
    """
    Forecast future sentiment for a place
    
    Args:
        place_id: The place ID to forecast
        forecast_days: Number of days to forecast (default: 7)
    
    Returns:
        ApiResponse: Sentiment forecast
    """
    try:
        result = prediction_service.forecast_sentiment(place_id, forecast_days)
        return ApiResponse(
            success=True,
            status_code=200,
            message="Forecast completed",
            data=result
        )
    except ValueError as e:
        logger.warning(f"Forecast validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Forecast failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Forecast failed: {str(e)}")


@router.post("/anomalies", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def detect_anomalies(
    place_id: int,
    threshold: float = Query(0.8, ge=0.5, le=1.0),
    prediction_service: PredictionService = Depends(get_prediction_service)
) -> ApiResponse:
    """
    Detect anomalies in sentiment patterns
    
    Args:
        place_id: The place ID to analyze
        threshold: Anomaly detection threshold (0.5-1.0, default: 0.8)
    
    Returns:
        ApiResponse: Detected anomalies
    """
    try:
        result = prediction_service.detect_anomalies(place_id, threshold)
        return ApiResponse(
            success=True,
            status_code=200,
            message="Anomaly detection completed",
            data=result
        )
    except ValueError as e:
        logger.warning(f"Anomaly detection validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {str(e)}")


@router.post("/batch-forecast", response_model=BatchOperationResponse, status_code=status.HTTP_200_OK)
async def batch_forecast(
    place_ids: List[int],
    forecast_days: int = Query(7, ge=1, le=90),
    prediction_service: PredictionService = Depends(get_prediction_service)
) -> BatchOperationResponse:
    """
    Batch forecast sentiment for multiple places
    
    Args:
        place_ids: List of place IDs
        forecast_days: Number of days to forecast (default: 7)
    
    Returns:
        BatchOperationResponse: Forecast results for all places
    """
    try:
        results = prediction_service.batch_forecast(place_ids, forecast_days)
        
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
        logger.warning(f"Batch forecast validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Batch forecast failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch forecast failed: {str(e)}")
