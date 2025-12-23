"""
ClusterRepository - K-Means clustering results data access.

Handles current cluster assignments, membership queries, movement tracking,
and cluster statistics.
"""

from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from database.models import PlaceClusters, Places
from .base import BaseRepository


class ClusterRepository(BaseRepository[PlaceClusters]):
    """Repository for Place Cluster assignments.

    Specializes in clustering queries, membership tracking, and movement analysis.
    """

    def __init__(self, session: Session):
        """Initialize ClusterRepository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, PlaceClusters)

    # =====================================================================
    # Cluster Assignment Queries
    # =====================================================================

    def find_by_place(self, place_id: str) -> Optional[PlaceClusters]:
        """Get current cluster for place.

        Args:
            place_id: Place identifier

        Returns:
            Current cluster assignment
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.place_id == place_id)
            .order_by(self.entity_class.assignment_date.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalars().first()

    def find_cluster_members(
        self, cluster_id: int, limit: int = 500
    ) -> List[PlaceClusters]:
        """Get all places in cluster.

        Args:
            cluster_id: Cluster identifier
            limit: Maximum results

        Returns:
            Places in cluster
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.cluster_id == cluster_id)
            .order_by(self.entity_class.distance_to_centroid.asc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_cluster_sizes(self) -> Dict[int, int]:
        """Get size of each cluster.

        Returns:
            Dict mapping cluster_id to member count
        """
        stmt = select(
            self.entity_class.cluster_id,
            func.count(self.entity_class.id).label("size"),
        ).group_by(self.entity_class.cluster_id)

        results = self.session.execute(stmt).all()
        return {cluster_id: size for cluster_id, size in results}

    def get_latest_clustering(self) -> Dict[int, List[str]]:
        """Get most recent cluster assignments.

        Returns:
            Dict mapping cluster_id to place_ids
        """
        # Get latest run
        latest_stmt = (
            select(self.entity_class)
            .order_by(self.entity_class.assignment_date.desc())
            .limit(1)
        )
        latest = self.session.execute(latest_stmt).scalars().first()

        if not latest:
            return {}

        # Get all from this run
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.assignment_date == latest.assignment_date)
        )
        assignments = self.session.execute(stmt).scalars().all()

        result = {}
        for assignment in assignments:
            if assignment.cluster_id not in result:
                result[assignment.cluster_id] = []
            result[assignment.cluster_id].append(assignment.place_id)

        return result

    # =====================================================================
    # Similarity & Distance Queries
    # =====================================================================

    def find_cluster_centroid_members(self, cluster_id: int, limit: int = 20) -> List[PlaceClusters]:
        """Get places closest to cluster centroid.

        Args:
            cluster_id: Cluster identifier
            limit: Number of central members

        Returns:
            Most representative places
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.cluster_id == cluster_id)
            .order_by(self.entity_class.distance_to_centroid.asc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_cluster_periphery(self, cluster_id: int, limit: int = 20) -> List[PlaceClusters]:
        """Get places farthest from cluster centroid (outliers).

        Args:
            cluster_id: Cluster identifier
            limit: Number of peripheral members

        Returns:
            Least representative places (outliers)
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.cluster_id == cluster_id)
            .order_by(self.entity_class.distance_to_centroid.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_distance_range(
        self, min_distance: float, max_distance: float, limit: int = 100
    ) -> List[PlaceClusters]:
        """Find assignments within distance range from centroid.

        Args:
            min_distance: Minimum distance
            max_distance: Maximum distance
            limit: Maximum results

        Returns:
            Assignments within range
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.distance_to_centroid >= min_distance,
                    self.entity_class.distance_to_centroid <= max_distance,
                )
            )
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Movement Tracking
    # =====================================================================

    def get_cluster_history(self, place_id: str) -> List[Dict[str, Any]]:
        """Get cluster assignment history for place.

        Args:
            place_id: Place identifier

        Returns:
            Historical assignments
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.place_id == place_id)
            .order_by(self.entity_class.assignment_date.asc())
        )
        assignments = self.session.execute(stmt).scalars().all()

        return [
            {
                "date": a.assignment_date,
                "cluster_id": a.cluster_id,
                "distance": a.distance_to_centroid,
            }
            for a in assignments
        ]

    def find_cluster_changes(self, place_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Find places that changed clusters recently.

        Args:
            place_ids: Optional list of places to check (if None, check all)

        Returns:
            Places with cluster changes
        """
        if place_ids:
            stmt = (
                select(self.entity_class)
                .where(self.entity_class.place_id.in_(place_ids))
                .order_by(self.entity_class.place_id, self.entity_class.assignment_date.desc())
            )
        else:
            stmt = select(self.entity_class).order_by(
                self.entity_class.place_id, self.entity_class.assignment_date.desc()
            )

        all_assignments = self.session.execute(stmt).scalars().all()

        changes = []
        place_tracking = {}

        for assignment in all_assignments:
            pid = assignment.place_id

            if pid not in place_tracking:
                place_tracking[pid] = assignment
            else:
                prev = place_tracking[pid]
                if prev.cluster_id != assignment.cluster_id:
                    changes.append({
                        "place_id": pid,
                        "from_cluster": assignment.cluster_id,
                        "to_cluster": prev.cluster_id,
                        "from_date": assignment.assignment_date,
                        "to_date": prev.assignment_date,
                    })

        return changes

    # =====================================================================
    # Cluster Characteristics
    # =====================================================================

    def get_cluster_statistics(self, cluster_id: int) -> Dict[str, Any]:
        """Get statistics for cluster.

        Args:
            cluster_id: Cluster identifier

        Returns:
            Cluster stats (size, avg distance, variance)
        """
        stmt = (
            select(
                func.count(self.entity_class.id).label("size"),
                func.avg(self.entity_class.distance_to_centroid).label("avg_distance"),
                func.min(self.entity_class.distance_to_centroid).label("min_distance"),
                func.max(self.entity_class.distance_to_centroid).label("max_distance"),
            )
            .where(self.entity_class.cluster_id == cluster_id)
        )

        result = self.session.execute(stmt).first()

        return {
            "size": int(result.size or 0),
            "avg_distance": float(result.avg_distance or 0),
            "min_distance": float(result.min_distance or 0),
            "max_distance": float(result.max_distance or 0),
        }

    def get_all_cluster_stats(self) -> Dict[int, Dict[str, Any]]:
        """Get statistics for all clusters.

        Returns:
            Stats per cluster
        """
        cluster_sizes = self.get_cluster_sizes()
        stats = {}

        for cluster_id in cluster_sizes.keys():
            stats[cluster_id] = self.get_cluster_statistics(cluster_id)

        return stats

    # =====================================================================
    # Similarity Queries
    # =====================================================================

    def find_similar_places(self, place_id: str, limit: int = 20) -> List[PlaceClusters]:
        """Find places similar to given place (same cluster).

        Args:
            place_id: Reference place
            limit: Maximum results

        Returns:
            Similar places
        """
        # Get place's cluster
        place_assignment = self.find_by_place(place_id)
        if not place_assignment:
            return []

        # Get other members of same cluster
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.cluster_id == place_assignment.cluster_id,
                    self.entity_class.place_id != place_id,
                )
            )
            .order_by(self.entity_class.distance_to_centroid.asc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_dissimilar_places(self, place_id: str, limit: int = 20) -> List[PlaceClusters]:
        """Find places dissimilar to given place (different clusters).

        Args:
            place_id: Reference place
            limit: Maximum results

        Returns:
            Dissimilar places
        """
        place_assignment = self.find_by_place(place_id)
        if not place_assignment:
            return []

        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.cluster_id != place_assignment.cluster_id,
                    self.entity_class.place_id != place_id,
                )
            )
            .order_by(self.entity_class.distance_to_centroid.asc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()
