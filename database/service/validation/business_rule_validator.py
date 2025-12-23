"""Business rule validation layer for state and quota management.

This module enforces application-level business rules such as state
transitions, duplicate prevention, quota enforcement, and resource limits.

Attributes:
    BusinessRuleValidator: Validates business rules and constraints.
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta

from database.service.base import ValidationException
from database.repository.unit_of_work import UnitOfWork


class BusinessRuleValidator:
    """Enforces business rules and application constraints.

    Validates state transitions, prevents duplicates, enforces quotas,
    and ensures data consistency per business logic.
    """

    def __init__(self, unit_of_work: UnitOfWork) -> None:
        """Initialize business rule validator.

        Args:
            unit_of_work: UnitOfWork instance for repository access.
        """
        self.unit_of_work = unit_of_work

    def validate_no_duplicate_analysis(
        self,
        place_id: int,
        analysis_type: str,
        hours_back: int = 1,
    ) -> bool:
        """Validate no recent duplicate analysis exists.

        Prevents redundant analyses within a time window.

        Args:
            place_id: The place ID.
            analysis_type: Type of analysis (e.g., 'nlp', 'prediction').
            hours_back: Lookback window in hours (default: 1).

        Returns:
            True if no duplicate found.

        Raises:
            ValidationException: If duplicate analysis detected.
        """
        run_repo = self.unit_of_work.analytics_runs
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

        recent_runs = run_repo.find_recent(
            place_id=place_id,
            analysis_type=analysis_type,
            since=cutoff_time,
            status='completed',
        )

        if recent_runs:
            most_recent = recent_runs[0]
            raise ValidationException(
                f"Duplicate analysis blocked: {analysis_type} already "
                f"completed for place {place_id} at "
                f"{most_recent.completed_at.isoformat()}",
                field="analysis_type",
                value=analysis_type,
                context={
                    "constraint": (
                        f"only one {analysis_type} per {hours_back}h "
                        "allowed"
                    ),
                    "last_run": most_recent.completed_at.isoformat(),
                    "place_id": place_id,
                },
            )

        return True

    def validate_pipeline_state_transition(
        self,
        run_id: int,
        from_state: str,
        to_state: str,
    ) -> bool:
        """Validate state transition is valid.

        Enforces valid pipeline state machine transitions.

        Args:
            run_id: The analysis run ID.
            from_state: Current state.
            to_state: Desired new state.

        Returns:
            True if transition is valid.

        Raises:
            ValidationException: If transition invalid.
        """
        # Define valid transitions
        valid_transitions: Dict[str, List[str]] = {
            'pending': ['running', 'cancelled'],
            'running': ['completed', 'failed', 'paused'],
            'paused': ['running', 'cancelled'],
            'completed': [],  # Terminal state
            'failed': ['running'],  # Can retry
            'cancelled': [],  # Terminal state
        }

        if from_state not in valid_transitions:
            raise ValidationException(
                f"Unknown state: {from_state}",
                field="from_state",
                value=from_state,
                context={
                    "valid_states": list(valid_transitions.keys()),
                },
            )

        allowed_transitions = valid_transitions[from_state]

        if to_state not in allowed_transitions:
            raise ValidationException(
                f"Invalid transition: {from_state} -> {to_state}",
                field="to_state",
                value=to_state,
                context={
                    "current_state": from_state,
                    "allowed_transitions": allowed_transitions,
                    "constraint": f"{from_state} can only transition to "
                                  f"{allowed_transitions}",
                },
            )

        return True

    def validate_concurrent_run_limit(
        self,
        place_id: int,
        max_concurrent: int = 3,
    ) -> bool:
        """Validate place does not exceed concurrent run limit.

        Prevents resource exhaustion from too many simultaneous analyses.

        Args:
            place_id: The place ID.
            max_concurrent: Maximum concurrent runs (default: 3).

        Returns:
            True if under limit.

        Raises:
            ValidationException: If limit exceeded.
        """
        run_repo = self.unit_of_work.analytics_runs
        running_runs = run_repo.find_by_status_and_place(
            status='running',
            place_id=place_id,
        )

        current_running = len(running_runs)

        if current_running >= max_concurrent:
            raise ValidationException(
                f"Concurrent run limit exceeded for place {place_id}: "
                f"{current_running} >= {max_concurrent}",
                field="place_id",
                value=place_id,
                context={
                    "constraint": f"max_concurrent <= {max_concurrent}",
                    "current_running": current_running,
                    "max_allowed": max_concurrent,
                },
            )

        return True

    def validate_resource_quota(
        self,
        quota_type: str,
        usage: int,
        quota_limit: int,
    ) -> bool:
        """Validate resource usage within quota.

        Args:
            quota_type: Type of quota (e.g., 'cache_memory', 'analyses').
            usage: Current usage.
            quota_limit: Maximum allowed usage.

        Returns:
            True if within quota.

        Raises:
            ValidationException: If quota exceeded.
        """
        if usage >= quota_limit:
            raise ValidationException(
                f"Quota exceeded for {quota_type}: {usage} >= "
                f"{quota_limit}",
                field="quota_type",
                value=quota_type,
                context={
                    "constraint": f"{quota_type} usage <= {quota_limit}",
                    "current_usage": usage,
                    "quota_limit": quota_limit,
                    "quota_type": quota_type,
                },
            )

        return True

    def validate_analysis_prerequisites(
        self,
        place_id: int,
        analysis_type: str,
    ) -> bool:
        """Validate prerequisites are met for analysis type.

        Different analysis types have different data requirements.

        Args:
            place_id: The place ID.
            analysis_type: Type of analysis.

        Returns:
            True if prerequisites met.

        Raises:
            ValidationException: If prerequisites not met.
        """
        prerequisites: Dict[str, Dict[str, int]] = {
            'nlp': {'min_reviews': 5},
            'prediction': {'min_reviews': 20, 'min_days': 30},
            'correlation': {'min_reviews': 50},
            'clustering': {'min_places': 10},
            'patterns': {'min_reviews': 10},
        }

        if analysis_type not in prerequisites:
            # Unknown analysis types bypass this check
            return True

        reqs = prerequisites[analysis_type]

        # Check review count requirement
        if 'min_reviews' in reqs:
            review_repo = self.unit_of_work.reviews
            reviews = review_repo.find_by_place(place_id)
            if len(reviews) < reqs['min_reviews']:
                raise ValidationException(
                    f"Insufficient reviews for {analysis_type}: "
                    f"{len(reviews)} < {reqs['min_reviews']}",
                    field="analysis_type",
                    value=analysis_type,
                    context={
                        "constraint": (
                            f"{analysis_type} requires "
                            f"{reqs['min_reviews']} reviews"
                        ),
                        "actual_reviews": len(reviews),
                        "required_reviews": reqs['min_reviews'],
                    },
                )

        # Check data age requirement
        if 'min_days' in reqs:
            review_repo = self.unit_of_work.reviews
            reviews = review_repo.find_by_place(place_id)
            if reviews:
                oldest = min(reviews, key=lambda r: r.review_date)
                days_old = (
                    datetime.utcnow().date() -
                    oldest.review_date.date()
                ).days
                if days_old < reqs['min_days']:
                    raise ValidationException(
                        f"Data not old enough for {analysis_type}: "
                        f"{days_old} < {reqs['min_days']} days",
                        field="analysis_type",
                        value=analysis_type,
                        context={
                            "constraint": (
                                f"{analysis_type} requires "
                                f"{reqs['min_days']} days of data"
                            ),
                            "actual_days": days_old,
                            "required_days": reqs['min_days'],
                        },
                    )

        return True

    def validate_data_consistency(
        self,
        entity_type: str,
        entity_id: int,
    ) -> bool:
        """Validate entity data is consistent and not corrupted.

        Checks for logical inconsistencies that indicate data corruption.

        Args:
            entity_type: Type of entity.
            entity_id: ID of entity to check.

        Returns:
            True if data is consistent.

        Raises:
            ValidationException: If data inconsistencies detected.
        """
        if entity_type == 'Place':
            place_repo = self.unit_of_work.places
            place = place_repo.get_by_id(entity_id)

            if place is None:
                return True  # Entity doesn't exist, not our concern here

            # Verify place has valid name and location
            if (not hasattr(place, 'name') or not place.name or
                not hasattr(place, 'location') or not place.location):
                raise ValidationException(
                    f"Place {entity_id} has missing required fields",
                    field="entity_id",
                    value=entity_id,
                    context={
                        "entity_type": "Place",
                        "missing_fields": (
                            [] if place.name else ["name"] +
                            ([] if place.location else ["location"])
                        ),
                    },
                )

        elif entity_type == 'Review':
            review_repo = self.unit_of_work.reviews
            review = review_repo.get_by_id(entity_id)

            if review is None:
                return True

            # Verify review has place and valid rating
            if (not hasattr(review, 'place_id') or not review.place_id or
                not hasattr(review, 'rating') or
                review.rating is None or review.rating < 0 or
                review.rating > 5):
                raise ValidationException(
                    f"Review {entity_id} has invalid data",
                    field="entity_id",
                    value=entity_id,
                    context={
                        "entity_type": "Review",
                        "place_id": getattr(review, 'place_id', None),
                        "rating": getattr(review, 'rating', None),
                    },
                )

        return True

    def validate_anomaly_threshold(
        self,
        value: float,
        threshold: float,
        direction: str = "above",
    ) -> bool:
        """Validate value exceeds anomaly threshold.

        Args:
            value: The value to check.
            threshold: The anomaly threshold.
            direction: Check "above" or "below" threshold.

        Returns:
            True if value qualifies as anomalous.

        Raises:
            ValidationException: If not anomalous (for strict validation).
        """
        if direction == "above":
            if value <= threshold:
                return False  # Not anomalous
        elif direction == "below":
            if value >= threshold:
                return False  # Not anomalous
        else:
            raise ValidationException(
                f"Invalid anomaly direction: {direction}",
                field="direction",
                value=direction,
                context={
                    "allowed_values": ["above", "below"],
                },
            )

        return True

    def validate_place_modification_allowed(
        self,
        place_id: int,
        modification_type: str = "update",
    ) -> bool:
        """Validate place can be modified (not archived/deleted).

        Args:
            place_id: The place ID.
            modification_type: Type of modification.

        Returns:
            True if modification allowed.

        Raises:
            ValidationException: If place cannot be modified.
        """
        place_repo = self.unit_of_work.places
        place = place_repo.get_by_id(place_id)

        if place is None:
            raise ValidationException(
                f"Place not found: {place_id}",
                field="place_id",
                value=place_id,
                context={"entity_type": "Place"},
            )

        # Check if place is archived or deleted
        is_active = getattr(place, 'is_active', True)
        is_archived = getattr(place, 'is_archived', False)

        if is_archived:
            raise ValidationException(
                f"Cannot {modification_type} archived place: {place_id}",
                field="place_id",
                value=place_id,
                context={
                    "constraint": "place must not be archived",
                    "entity_type": "Place",
                },
            )

        if not is_active:
            raise ValidationException(
                f"Cannot {modification_type} inactive place: {place_id}",
                field="place_id",
                value=place_id,
                context={
                    "constraint": "place must be active",
                    "entity_type": "Place",
                },
            )

        return True


__all__ = ["BusinessRuleValidator"]
