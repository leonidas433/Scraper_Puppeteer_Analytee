"""Test fixtures and mock factories for service tests.

Provides factory functions and fixtures for creating test data.
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any

from database.service.dto import (
    DateRangeDTO,
    NLPResultDTO,
    ForecastDTO,
    CorrelationResultDTO,
    ClusterDTO,
    PatternDTO,
    TrendDTO,
    AnomalyDTO,
)


class DtoFactory:
    """Factory for creating test DTOs."""

    @staticmethod
    def create_date_range_dto(
        days_back: int = 30,
    ) -> DateRangeDTO:
        """Create a date range DTO for testing.

        Args:
            days_back: Number of days in past for start date.

        Returns:
            DateRangeDTO for testing.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        return DateRangeDTO(start_date, end_date)

    @staticmethod
    def create_trend_dto(
        direction: str = "up",
        strength: float = 0.75,
    ) -> TrendDTO:
        """Create a trend DTO for testing.

        Args:
            direction: Trend direction.
            strength: Trend strength.

        Returns:
            TrendDTO for testing.
        """
        return TrendDTO(
            direction=direction,
            strength=strength,
            start_value=100.0,
            end_value=125.0,
            change_percent=25.0,
        )

    @staticmethod
    def create_anomaly_dto(
        anomaly_id: int = 1,
    ) -> AnomalyDTO:
        """Create an anomaly DTO for testing.

        Args:
            anomaly_id: ID for anomaly.

        Returns:
            AnomalyDTO for testing.
        """
        return AnomalyDTO(
            anomaly_id=anomaly_id,
            timestamp=datetime.utcnow(),
            value=500.0,
            expected_range=(50.0, 150.0),
            severity=4,
            description="Test anomaly",
        )

    @staticmethod
    def create_forecast_dto(
        metric_name: str = "rating",
    ) -> ForecastDTO:
        """Create a forecast DTO for testing.

        Args:
            metric_name: Name of metric.

        Returns:
            ForecastDTO for testing.
        """
        forecast_values = [4.5, 4.6, 4.55, 4.7]
        confidence_intervals = [
            (4.3, 4.7),
            (4.4, 4.8),
            (4.35, 4.75),
            (4.5, 4.9),
        ]

        return ForecastDTO(
            metric_name=metric_name,
            forecast_values=forecast_values,
            confidence_intervals=confidence_intervals,
            trend="up",
            model_r_squared=0.92,
        )

    @staticmethod
    def create_correlation_dto(
        source: str = "rating",
        target: str = "review_count",
    ) -> CorrelationResultDTO:
        """Create a correlation DTO for testing.

        Args:
            source: Source metric name.
            target: Target metric name.

        Returns:
            CorrelationResultDTO for testing.
        """
        return CorrelationResultDTO(
            source_metric=source,
            target_metric=target,
            correlation_coefficient=0.78,
            p_value=0.001,
            lag_days=0,
            interpretation="strong positive correlation",
        )

    @staticmethod
    def create_cluster_dto(
        cluster_id: int = 1,
        place_count: int = 5,
    ) -> ClusterDTO:
        """Create a cluster DTO for testing.

        Args:
            cluster_id: Cluster ID.
            place_count: Number of places in cluster.

        Returns:
            ClusterDTO for testing.
        """
        place_ids = list(range(1, place_count + 1))
        centroid = {
            "avg_rating": 4.5,
            "review_count": 150,
            "sentiment": 0.65,
        }
        characteristics = {
            "performance": "high",
            "size": "medium",
            "stability": "stable",
        }

        return ClusterDTO(
            cluster_id=cluster_id,
            places=place_ids,
            centroid=centroid,
            silhouette_score=0.68,
            characteristics=characteristics,
        )

    @staticmethod
    def create_pattern_dto(
        pattern_id: int = 1,
        keyword: str = "wifi",
    ) -> PatternDTO:
        """Create a pattern DTO for testing.

        Args:
            pattern_id: Pattern ID.
            keyword: Pattern keyword.

        Returns:
            PatternDTO for testing.
        """
        return PatternDTO(
            pattern_id=pattern_id,
            keyword=keyword,
            frequency=25,
            first_seen=datetime.utcnow() - timedelta(days=30),
            last_seen=datetime.utcnow(),
            sentiment_correlation=-0.42,
            affected_places=[1, 2, 3],
        )

    @staticmethod
    def create_nlp_result_dto(
        analysis_id: int = 1,
        place_id: int = 1,
    ) -> NLPResultDTO:
        """Create an NLP result DTO for testing.

        Args:
            analysis_id: Analysis ID.
            place_id: Place ID.

        Returns:
            NLPResultDTO for testing.
        """
        return NLPResultDTO(
            analysis_id=analysis_id,
            place_id=place_id,
            overall_sentiment=0.65,
            emotion_scores={
                "joy": 0.45,
                "anger": 0.15,
                "surprise": 0.20,
            },
            key_insights=[
                "Customers love the service",
                "WiFi quality needs improvement",
            ],
            sentiment_trend=DtoFactory.create_trend_dto(),
            anomalies=[DtoFactory.create_anomaly_dto()],
        )


class MockUnitOfWork:
    """Mock UnitOfWork for testing services."""

    def __init__(self) -> None:
        """Initialize mock unit of work."""
        self._in_transaction = False
        self._committed = False

    def begin(self) -> None:
        """Start mock transaction."""
        self._in_transaction = True

    def commit(self) -> None:
        """Commit mock transaction."""
        if self._in_transaction:
            self._committed = True
            self._in_transaction = False

    def rollback(self) -> None:
        """Rollback mock transaction."""
        self._in_transaction = False
        self._committed = False

    @property
    def in_transaction(self) -> bool:
        """Check if in transaction."""
        return self._in_transaction

    @property
    def committed(self) -> bool:
        """Check if last transaction committed."""
        return self._committed


__all__ = ["DtoFactory", "MockUnitOfWork"]
