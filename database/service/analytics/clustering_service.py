"""Clustering Service - K-means clustering and group analysis."""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from database.service.base import BaseService
from database.service.validation.input_validator import InputValidator


logger = logging.getLogger(__name__)


class ClusteringService(BaseService):
    """Performs K-means clustering on places."""

    def cluster_places(
        self,
        place_ids: List[int],
        n_clusters: int = 3,
        features: Optional[List[str]] = None,
    ):
        """Perform K-means clustering on places."""
        if not place_ids or len(place_ids) < n_clusters:
            raise ValueError(f"Need at least {n_clusters} places")

        cache_key = f"{self.__class__.__name__}.cluster.{len(place_ids)}.{n_clusters}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            with self._transaction():
                places = [self._uow.places.get(pid) for pid in place_ids]
                places = [p for p in places if p is not None]

                if len(places) < n_clusters:
                    raise ValueError(f"Insufficient places for {n_clusters} clusters")

                feature_matrix = []
                for place in places:
                    row = [float(getattr(place, 'avg_rating', 0) or 0),
                           float(getattr(place, 'review_count', 0) or 0)]
                    feature_matrix.append(row)

                X = np.array(feature_matrix)
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)

                kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                labels = kmeans.fit_predict(X_scaled)

                clusters = {}
                for idx, label in enumerate(labels):
                    if label not in clusters:
                        clusters[label] = []
                    clusters[label].append(places[idx].id)

                result = {
                    "timestamp": datetime.utcnow(),
                    "n_clusters": n_clusters,
                    "total_places": len(places),
                    "clusters": clusters,
                    "inertia": float(kmeans.inertia_),
                }

                self._cache.set(cache_key, result, ttl_seconds=86400)
                logger.info(f"Clustered {len(places)} places into {n_clusters} clusters")
                return result

        except Exception as e:
            logger.error(f"Clustering error: {str(e)}")
            raise

    def get_cluster_for_place(
        self,
        place_id: int,
        reference_place_ids: List[int],
        n_clusters: int = 3,
    ) -> int:
        """Get cluster assignment for a specific place."""
        InputValidator.validate_id(place_id, "place_id")

        try:
            result = self.cluster_places(reference_place_ids + [place_id], n_clusters)
            
            clusters = result.get("clusters", {})
            for cluster_id, places in clusters.items():
                if place_id in places:
                    return cluster_id
            
            return -1

        except Exception as e:
            logger.error(f"Cluster lookup error: {str(e)}")
            return -1

    def batch_cluster_analysis(
        self,
        place_groups: Dict[str, List[int]],
        n_clusters: int = 3,
    ):
        """Cluster multiple groups of places independently."""
        results = {}
        
        for group_name, place_ids in place_groups.items():
            try:
                results[group_name] = self.cluster_places(place_ids, n_clusters)
            except Exception as e:
                logger.error(f"Batch clustering failed for {group_name}: {str(e)}")
        
        return results
