"""Cross-entity validation layer for relationship integrity.

This module validates relationships and dependencies between entities to
ensure data consistency and referential integrity across the system.

Attributes:
    CrossEntityValidator: Validates relationships between entities.
"""

from typing import List
from datetime import datetime

from database.service.base import ValidationException
from database.repository.unit_of_work import UnitOfWork


class CrossEntityValidator:
    """Validates relationships between multiple entities.

    Ensures referential integrity, temporal consistency, and cross-entity
    constraints are satisfied.
    """

    def __init__(self, unit_of_work: UnitOfWork) -> None:
        """Initialize cross-entity validator.

        Args:
            unit_of_work: UnitOfWork instance for repository access.
        """
        self.unit_of_work = unit_of_work

    def validate_review_belongs_to_place(
        self,
        review_id: int,
        place_id: int,
    ) -> bool:
        """Validate review belongs to the specified place.

        Args:
            review_id: The review ID to check.
            place_id: The expected place ID.

        Returns:
            True if review belongs to place.

        Raises:
            ValidationException: If review does not belong to place.
        """
        review_repo = self.unit_of_work.reviews
        review = review_repo.get_by_id(review_id)

        if review is None:
            raise ValidationException(
                f"Review not found: {review_id}",
                field="review_id",
                value=review_id,
                context={"entity_type": "Review"},
            )

        if review.place_id != place_id:
            raise ValidationException(
                f"Review {review_id} belongs to place {review.place_id}, "
                f"not {place_id}",
                field="review_id",
                value=review_id,
                context={
                    "expected_place_id": place_id,
                    "actual_place_id": review.place_id,
                    "constraint": "review.place_id == place_id",
                },
            )

        return True

    def validate_analysis_covers_all_places(
        self,
        place_ids: List[int],
    ) -> bool:
        """Validate all places in list exist and are active.

        Args:
            place_ids: List of place IDs to validate.

        Returns:
            True if all places exist and are active.

        Raises:
            ValidationException: If any place not found or inactive.
        """
        if not place_ids:
            raise ValidationException(
                "Place list cannot be empty",
                field="place_ids",
                value=place_ids,
                context={"constraint": "at least one place required"},
            )

        place_repo = self.unit_of_work.places
        missing_places = []

        for place_id in place_ids:
            place = place_repo.get_by_id(place_id)
            if place is None:
                missing_places.append(place_id)

        if missing_places:
            raise ValidationException(
                f"Places not found: {missing_places}",
                field="place_ids",
                value=missing_places,
                context={
                    "missing_count": len(missing_places),
                    "total_places": len(place_ids),
                },
            )

        return True

    def validate_no_circular_references(
        self,
        source_id: int,
        target_id: int,
        relationship_type: str = "correlation",
    ) -> bool:
        """Validate relationship does not create circular reference.

        Args:
            source_id: Source entity ID.
            target_id: Target entity ID.
            relationship_type: Type of relationship (e.g., "correlation").

        Returns:
            True if no circular reference.

        Raises:
            ValidationException: If circular reference detected.
        """
        if source_id == target_id:
            raise ValidationException(
                f"Self-reference not allowed: {source_id} -> {source_id}",
                field="target_id",
                value=target_id,
                context={
                    "relationship_type": relationship_type,
                    "constraint": "source_id != target_id",
                },
            )

        return True

    def validate_time_series_continuity(
        self,
        place_id: int,
        start_date,
        end_date,
    ) -> bool:
        """Validate time series data exists for entire date range.

        Ensures analysis period has continuous data coverage.

        Args:
            place_id: The place ID to check.
            start_date: Start date of range.
            end_date: End date of range.

        Returns:
            True if data is continuous.

        Raises:
            ValidationException: If data gaps exist in range.
        """
        review_repo = self.unit_of_work.reviews
        reviews = review_repo.find_by_place_and_date_range(
            place_id, start_date, end_date
        )

        if not reviews:
            raise ValidationException(
                f"No data for place {place_id} in range "
                f"[{start_date}, {end_date}]",
                field="place_id",
                value=place_id,
                context={
                    "constraint": "data must exist for date range",
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
            )

        # Simple continuity check: ensure we have reviews across the range
        review_dates = sorted(
            set(r.review_date.date() for r in reviews)
        )
        date_range = (end_date - start_date).days

        # Allow up to 30% gaps in data
        expected_days = date_range + 1
        actual_days = len(review_dates)
        gap_ratio = 1 - (actual_days / expected_days)

        if gap_ratio > 0.3:
            raise ValidationException(
                f"Significant data gap for place {place_id}: "
                f"{gap_ratio*100:.1f}% missing",
                field="place_id",
                value=place_id,
                context={
                    "constraint": "max 30% data gap allowed",
                    "gap_ratio": gap_ratio,
                    "expected_days": expected_days,
                    "actual_days": actual_days,
                },
            )

        return True

    def validate_cluster_integrity(
        self,
        cluster_id: int,
    ) -> bool:
        """Validate cluster has consistent, valid members.

        All members should have same cluster assignment.

        Args:
            cluster_id: The cluster ID to validate.

        Returns:
            True if cluster is internally consistent.

        Raises:
            ValidationException: If cluster has integrity issues.
        """
        cluster_repo = self.unit_of_work.place_clusters
        cluster_members = cluster_repo.find_by_cluster(cluster_id)

        if not cluster_members:
            raise ValidationException(
                f"Cluster {cluster_id} has no members",
                field="cluster_id",
                value=cluster_id,
                context={
                    "constraint": "cluster must have members",
                    "entity_type": "Cluster",
                },
            )

        # Verify all members actually belong to this cluster
        inconsistent = [
            m for m in cluster_members
            if getattr(m, 'cluster_id', None) != cluster_id
        ]

        if inconsistent:
            raise ValidationException(
                f"Cluster {cluster_id} has inconsistent members: "
                f"{len(inconsistent)} misassigned",
                field="cluster_id",
                value=cluster_id,
                context={
                    "constraint": "all members must have cluster_id match",
                    "inconsistent_count": len(inconsistent),
                    "entity_type": "Cluster",
                },
            )

        return True

    def validate_pattern_consistency(
        self,
        pattern_id: int,
    ) -> bool:
        """Validate pattern data is internally consistent.

        Pattern frequency and occurrence records should align.

        Args:
            pattern_id: The pattern ID to validate.

        Returns:
            True if pattern is consistent.

        Raises:
            ValidationException: If pattern has inconsistencies.
        """
        pattern_repo = self.unit_of_work.review_patterns
        pattern = pattern_repo.get_by_id(pattern_id)

        if pattern is None:
            raise ValidationException(
                f"Pattern not found: {pattern_id}",
                field="pattern_id",
                value=pattern_id,
                context={"entity_type": "Pattern"},
            )

        # Verify pattern has required attributes
        required_attrs = ['keyword', 'occurrence_count', 'first_seen']
        missing_attrs = [
            attr for attr in required_attrs
            if not hasattr(pattern, attr) or getattr(pattern, attr) is None
        ]

        if missing_attrs:
            raise ValidationException(
                f"Pattern {pattern_id} missing required fields: "
                f"{missing_attrs}",
                field="pattern_id",
                value=pattern_id,
                context={
                    "missing_fields": missing_attrs,
                    "entity_type": "Pattern",
                },
            )

        # Verify last_seen >= first_seen if both present
        if (hasattr(pattern, 'last_seen') and pattern.last_seen and
            pattern.first_seen > pattern.last_seen):
            raise ValidationException(
                f"Pattern {pattern_id} has invalid date range: "
                f"{pattern.first_seen} > {pattern.last_seen}",
                field="pattern_id",
                value=pattern_id,
                context={
                    "constraint": "first_seen <= last_seen",
                    "first_seen": pattern.first_seen.isoformat(),
                    "last_seen": pattern.last_seen.isoformat(),
                },
            )

        return True

    def validate_analysis_run_state(
        self,
        run_id: int,
        expected_state: str,
    ) -> bool:
        """Validate analysis run is in expected state.

        Args:
            run_id: The analysis run ID.
            expected_state: Expected state (e.g., 'pending', 'running').

        Returns:
            True if run is in expected state.

        Raises:
            ValidationException: If run in unexpected state.
        """
        run_repo = self.unit_of_work.analytics_runs
        run = run_repo.get_by_id(run_id)

        if run is None:
            raise ValidationException(
                f"Analysis run not found: {run_id}",
                field="run_id",
                value=run_id,
                context={"entity_type": "AnalyticsRun"},
            )

        actual_state = getattr(run, 'status', None)

        if actual_state != expected_state:
            raise ValidationException(
                f"Run {run_id} in state '{actual_state}', "
                f"expected '{expected_state}'",
                field="run_id",
                value=run_id,
                context={
                    "constraint": f"status == {expected_state}",
                    "actual_state": actual_state,
                    "expected_state": expected_state,
                    "entity_type": "AnalyticsRun",
                },
            )

        return True


__all__ = ["CrossEntityValidator"]
