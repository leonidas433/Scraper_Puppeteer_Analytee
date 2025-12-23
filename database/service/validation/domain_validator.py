"""Domain validation layer for business rule enforcement.

This module validates business rules that depend on database state or
domain-specific constraints. These validations require access to
repositories and should be performed before business logic execution.

Attributes:
    DomainValidator: Validates domain-specific business rules.
"""

from typing import Any, Optional
from datetime import datetime, timedelta

from database.service.base import ValidationException
from database.repository.unit_of_work import UnitOfWork


class DomainValidator:
    """Validates domain-specific constraints and business rules.

    Validates conditions that require database queries or domain knowledge,
    such as entity existence, data sufficiency, and constraint satisfaction.
    """

    def __init__(self, unit_of_work: UnitOfWork) -> None:
        """Initialize domain validator.

        Args:
            unit_of_work: UnitOfWork instance for repository access.
        """
        self.unit_of_work = unit_of_work

    def validate_place_exists(self, place_id: int) -> bool:
        """Validate place with given ID exists in database.

        Args:
            place_id: The place ID to check.

        Returns:
            True if place exists.

        Raises:
            ValidationException: If place does not exist.
        """
        place_repo = self.unit_of_work.places
        place = place_repo.get_by_id(place_id)

        if place is None:
            raise ValidationException(
                f"Place not found: {place_id}",
                field="place_id",
                value=place_id,
                context={
                    "entity_type": "Place",
                    "constraint": "entity must exist",
                },
            )

        return True

    def validate_review_exists(self, review_id: int) -> bool:
        """Validate review with given ID exists in database.

        Args:
            review_id: The review ID to check.

        Returns:
            True if review exists.

        Raises:
            ValidationException: If review does not exist.
        """
        review_repo = self.unit_of_work.reviews
        review = review_repo.get_by_id(review_id)

        if review is None:
            raise ValidationException(
                f"Review not found: {review_id}",
                field="review_id",
                value=review_id,
                context={
                    "entity_type": "Review",
                    "constraint": "entity must exist",
                },
            )

        return True

    def validate_sufficient_historical_data(
        self,
        place_id: int,
        min_reviews: int = 10,
        min_days: int = 7,
    ) -> bool:
        """Validate place has sufficient historical data for analysis.

        Analysis requires minimum number of reviews spanning minimum timeframe
        to produce meaningful results.

        Args:
            place_id: The place ID to check.
            min_reviews: Minimum required reviews (default: 10).
            min_days: Minimum required days of data (default: 7).

        Returns:
            True if sufficient data exists.

        Raises:
            ValidationException: If insufficient historical data.
        """
        # Validate place exists first
        self.validate_place_exists(place_id)

        review_repo = self.unit_of_work.reviews
        reviews = review_repo.find_by_place(place_id)

        if len(reviews) < min_reviews:
            raise ValidationException(
                f"Insufficient reviews for place {place_id}: {len(reviews)} "
                f"< {min_reviews}",
                field="place_id",
                value=place_id,
                context={
                    "constraint": f"min_reviews >= {min_reviews}",
                    "actual_reviews": len(reviews),
                    "entity_type": "Place",
                },
            )

        if reviews:
            oldest_review = min(
                reviews, key=lambda r: r.review_date
            )
            days_span = (
                datetime.utcnow().date() -
                oldest_review.review_date.date()
            ).days

            if days_span < min_days:
                raise ValidationException(
                    f"Insufficient data span for place {place_id}: "
                    f"{days_span} < {min_days} days",
                    field="place_id",
                    value=place_id,
                    context={
                        "constraint": f"data_span >= {min_days} days",
                        "actual_days": days_span,
                        "oldest_review": oldest_review.review_date.isoformat(),
                        "entity_type": "Place",
                    },
                )

        return True

    def validate_sentiment_score_range(
        self,
        score: float,
        field_name: str = "sentiment_score",
        min_score: float = -1.0,
        max_score: float = 1.0,
    ) -> bool:
        """Validate sentiment score is within valid range.

        Args:
            score: The sentiment score to validate.
            field_name: Name of field for error messages.
            min_score: Minimum valid score (default: -1.0).
            max_score: Maximum valid score (default: 1.0).

        Returns:
            True if score is in valid range.

        Raises:
            ValidationException: If score out of range.
        """
        if score < min_score or score > max_score:
            raise ValidationException(
                f"{field_name} out of range: {score} not in "
                f"[{min_score}, {max_score}]",
                field=field_name,
                value=score,
                context={
                    "valid_range": [min_score, max_score],
                    "actual_score": score,
                    "constraint": f"{min_score} <= score <= {max_score}",
                },
            )

        return True

    def validate_confidence_score_range(
        self,
        confidence: float,
        field_name: str = "confidence",
        min_confidence: float = 0.0,
        max_confidence: float = 1.0,
    ) -> bool:
        """Validate confidence/probability score is in 0-1 range.

        Args:
            confidence: The confidence score to validate.
            field_name: Name of field for error messages.
            min_confidence: Minimum score (default: 0.0).
            max_confidence: Maximum score (default: 1.0).

        Returns:
            True if confidence is in valid range.

        Raises:
            ValidationException: If confidence out of range.
        """
        if confidence < min_confidence or confidence > max_confidence:
            raise ValidationException(
                f"{field_name} invalid probability: {confidence} not in "
                f"[{min_confidence}, {max_confidence}]",
                field=field_name,
                value=confidence,
                context={
                    "valid_range": [min_confidence, max_confidence],
                    "actual_confidence": confidence,
                    "constraint": (
                        f"{min_confidence} <= confidence <= "
                        f"{max_confidence}"
                    ),
                },
            )

        return True

    def validate_cluster_size(
        self,
        cluster_id: int,
        min_size: int = 2,
        max_size: int = 1000,
    ) -> bool:
        """Validate cluster has valid size.

        Clusters should have meaningful size: not too small (noise) and
        not too large (ineffective grouping).

        Args:
            cluster_id: The cluster ID to validate.
            min_size: Minimum cluster size (default: 2).
            max_size: Maximum cluster size (default: 1000).

        Returns:
            True if cluster size is valid.

        Raises:
            ValidationException: If cluster size invalid.
        """
        cluster_repo = self.unit_of_work.place_clusters
        places_in_cluster = cluster_repo.find_by_cluster(cluster_id)
        cluster_size = len(places_in_cluster)

        if cluster_size < min_size:
            raise ValidationException(
                f"Cluster {cluster_id} too small: {cluster_size} < "
                f"{min_size}",
                field="cluster_id",
                value=cluster_id,
                context={
                    "constraint": f"size >= {min_size}",
                    "actual_size": cluster_size,
                    "entity_type": "Cluster",
                },
            )

        if cluster_size > max_size:
            raise ValidationException(
                f"Cluster {cluster_id} too large: {cluster_size} > "
                f"{max_size}",
                field="cluster_id",
                value=cluster_id,
                context={
                    "constraint": f"size <= {max_size}",
                    "actual_size": cluster_size,
                    "entity_type": "Cluster",
                },
            )

        return True

    def validate_pattern_frequency(
        self,
        pattern_id: int,
        min_occurrences: int = 2,
    ) -> bool:
        """Validate pattern appears with sufficient frequency.

        Patterns with only single occurrence are not valid patterns.

        Args:
            pattern_id: The pattern ID to validate.
            min_occurrences: Minimum required occurrences (default: 2).

        Returns:
            True if pattern frequency is valid.

        Raises:
            ValidationException: If pattern too rare.
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

        occurrences = getattr(pattern, 'occurrence_count', 0)

        if occurrences < min_occurrences:
            raise ValidationException(
                f"Pattern {pattern_id} too rare: {occurrences} < "
                f"{min_occurrences}",
                field="pattern_id",
                value=pattern_id,
                context={
                    "constraint": f"occurrences >= {min_occurrences}",
                    "actual_occurrences": occurrences,
                    "entity_type": "Pattern",
                },
            )

        return True

    def validate_correlation_coefficient(
        self,
        correlation: float,
        field_name: str = "correlation",
        min_correlation: float = -1.0,
        max_correlation: float = 1.0,
    ) -> bool:
        """Validate correlation coefficient is in valid range.

        Pearson correlation is always in range [-1, 1].

        Args:
            correlation: The correlation coefficient.
            field_name: Name of field for error messages.
            min_correlation: Minimum value (default: -1.0).
            max_correlation: Maximum value (default: 1.0).

        Returns:
            True if correlation is in valid range.

        Raises:
            ValidationException: If correlation out of range.
        """
        if correlation < min_correlation or correlation > max_correlation:
            raise ValidationException(
                f"{field_name} invalid: {correlation} not in "
                f"[{min_correlation}, {max_correlation}]",
                field=field_name,
                value=correlation,
                context={
                    "valid_range": [min_correlation, max_correlation],
                    "actual_correlation": correlation,
                    "constraint": (
                        f"{min_correlation} <= correlation <= "
                        f"{max_correlation}"
                    ),
                },
            )

        return True

    def validate_k_clusters(
        self,
        k: int,
        min_k: int = 2,
        max_k: int = 100,
    ) -> bool:
        """Validate K parameter for K-means clustering.

        K should be reasonable for the expected dataset size.

        Args:
            k: Number of clusters.
            min_k: Minimum K value (default: 2).
            max_k: Maximum K value (default: 100).

        Returns:
            True if K is valid.

        Raises:
            ValidationException: If K out of valid range.
        """
        if k < min_k or k > max_k:
            raise ValidationException(
                f"K-clusters parameter invalid: {k} not in "
                f"[{min_k}, {max_k}]",
                field="k",
                value=k,
                context={
                    "valid_range": [min_k, max_k],
                    "actual_k": k,
                    "constraint": f"{min_k} <= k <= {max_k}",
                },
            )

        return True


__all__ = ["DomainValidator"]
