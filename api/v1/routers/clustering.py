"""Clustering Service API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from api.dependencies import get_clustering_service
from database.service.analytics import ClusteringService
from api.v1.schemas.common_schemas import ApiResponse, BatchOperationResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/clustering", tags=["clustering"])


@router.post("/cluster-places", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def cluster_places(
    place_ids: List[int],
    n_clusters: int = Query(3, ge=2, le=10),
    clustering_service: ClusteringService = Depends(get_clustering_service)
) -> ApiResponse:
    """
    Cluster a group of places
    
    Args:
        place_ids: List of place IDs to cluster
        n_clusters: Number of clusters (default: 3, range: 2-10)
    
    Returns:
        ApiResponse: Clustering results with place-to-cluster assignments
    """
    try:
        result = clustering_service.cluster_places(place_ids, n_clusters)
        return ApiResponse(
            success=True,
            status_code=200,
            message="Clustering completed",
            data=result
        )
    except ValueError as e:
        logger.warning(f"Clustering validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Clustering failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


@router.post("/place-cluster", response_model=ApiResponse, status_code=status.HTTP_200_OK)
async def get_place_cluster(
    place_id: int,
    reference_place_ids: List[int],
    n_clusters: int = Query(3, ge=2, le=10),
    clustering_service: ClusteringService = Depends(get_clustering_service)
) -> ApiResponse:
    """
    Get cluster assignment for a single place
    
    Args:
        place_id: The place ID to assign to a cluster
        reference_place_ids: Reference places to cluster against
        n_clusters: Number of clusters (default: 3)
    
    Returns:
        ApiResponse: Cluster assignment for the place
    """
    try:
        result = clustering_service.get_cluster_for_place(place_id, reference_place_ids, n_clusters)
        return ApiResponse(
            success=True,
            status_code=200,
            message="Cluster assignment retrieved",
            data=result
        )
    except ValueError as e:
        logger.warning(f"Cluster assignment validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Cluster assignment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cluster assignment failed: {str(e)}")


@router.post("/batch", response_model=BatchOperationResponse, status_code=status.HTTP_200_OK)
async def batch_cluster_analysis(
    place_groups: List[List[int]],
    n_clusters: int = Query(3, ge=2, le=10),
    clustering_service: ClusteringService = Depends(get_clustering_service)
) -> BatchOperationResponse:
    """
    Batch cluster analysis for multiple groups of places
    
    Args:
        place_groups: List of place ID lists to cluster independently
        n_clusters: Number of clusters per group (default: 3)
    
    Returns:
        BatchOperationResponse: Clustering results for all groups
    """
    try:
        results = clustering_service.batch_cluster_analysis(place_groups, n_clusters)
        
        failed = sum(1 for r in results if not r.get("success", True))
        success = len(results) - failed
        
        return BatchOperationResponse(
            total_items=len(place_groups),
            processed=success,
            failed=failed,
            success_rate=success / len(place_groups) if place_groups else 0,
            results=results
        )
    except ValueError as e:
        logger.warning(f"Batch clustering validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Batch clustering failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch clustering failed: {str(e)}")
