"""Transformer functions for converting between models and DTOs.

Provides functions to transform ORM models, engine outputs, and other
data into DTOs for API responses.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from database.service.dto.response_dto import (
    NLPResultDTO,
    TrendDTO,
    AnomalyDTO,
    ForecastDTO,
    CorrelationResultDTO,
    ClusterDTO,
    PatternDTO,
    AnalyticsRunDTO,
    ExecutiveSummaryDTO,
    KPIResultDTO,
    CacheEntryDTO,
)
from database.service.dto.common_dto import (
    InsightsDTO,
    TimeSeriesDataDTO,
    SummaryStatisticsDTO,
    ComparisonResultDTO,
)


class DTOTransformer:
    """Transforms models and engine outputs into DTOs."""

    @staticmethod
    def trend_to_dto(
        direction: str,
        strength: float,
        start_value: float,
        end_value: float,
    ) -> TrendDTO:
        """Transform trend data to DTO.

        Args:
            direction: 'up', 'down', or 'stable'.
            strength: Strength value 0-1.
            start_value: Value at start.
            end_value: Value at end.

        Returns:
            TrendDTO representation.
        """
        change_percent = (
            ((end_value - start_value) / start_value * 100)
            if start_value != 0 else 0.0
        )
        return TrendDTO(
            direction=direction,
            strength=strength,
            start_value=start_value,
            end_value=end_value,
            change_percent=change_percent,
        )

    @staticmethod
    def anomaly_to_dto(
        anomaly_id: int,
        timestamp: datetime,
        value: float,
        expected_low: float,
        expected_high: float,
        severity: int,
        description: str,
    ) -> AnomalyDTO:
        """Transform anomaly data to DTO.

        Args:
            anomaly_id: Unique anomaly ID.
            timestamp: When anomaly occurred.
            value: The anomalous value.
            expected_low: Lower bound of expected range.
            expected_high: Upper bound of expected range.
            severity: Severity 1-5.
            description: Anomaly description.

        Returns:
            AnomalyDTO representation.
        """
        return AnomalyDTO(
            anomaly_id=anomaly_id,
            timestamp=timestamp,
            value=value,
            expected_range=(expected_low, expected_high),
            severity=severity,
            description=description,
        )

    @staticmethod
    def forecast_to_dto(
        metric_name: str,
        forecast_values: List[float],
        confidence_intervals: List[tuple[float, float]],
        trend: str,
        r_squared: float,
    ) -> ForecastDTO:
        """Transform forecast data to DTO.

        Args:
            metric_name: Name of forecasted metric.
            forecast_values: Predicted values.
            confidence_intervals: Confidence bounds per value.
            trend: Overall trend direction.
            r_squared: Model quality metric.

        Returns:
            ForecastDTO representation.
        """
        return ForecastDTO(
            metric_name=metric_name,
            forecast_values=forecast_values,
            confidence_intervals=confidence_intervals,
            trend=trend,
            model_r_squared=r_squared,
        )

    @staticmethod
    def correlation_to_dto(
        source_metric: str,
        target_metric: str,
        coefficient: float,
        p_value: float,
        lag_days: int = 0,
    ) -> CorrelationResultDTO:
        """Transform correlation data to DTO.

        Args:
            source_metric: First metric name.
            target_metric: Second metric name.
            coefficient: Correlation coefficient.
            p_value: Statistical p-value.
            lag_days: Lag in days (default: 0).

        Returns:
            CorrelationResultDTO representation.
        """
        # Generate human-readable interpretation
        abs_coef = abs(coefficient)
        if abs_coef > 0.7:
            strength = "strong"
        elif abs_coef > 0.4:
            strength = "moderate"
        else:
            strength = "weak"

        direction = "positive" if coefficient > 0 else "negative"
        sig_text = "significant" if p_value < 0.05 else "not significant"

        interpretation = (
            f"{strength} {direction} correlation "
            f"({sig_text})"
        )

        return CorrelationResultDTO(
            source_metric=source_metric,
            target_metric=target_metric,
            correlation_coefficient=coefficient,
            p_value=p_value,
            lag_days=lag_days,
            interpretation=interpretation,
        )

    @staticmethod
    def cluster_to_dto(
        cluster_id: int,
        place_ids: List[int],
        centroid: Dict[str, float],
        silhouette: float,
        characteristics: Dict[str, str],
    ) -> ClusterDTO:
        """Transform cluster data to DTO.

        Args:
            cluster_id: Unique cluster ID.
            place_ids: Places in cluster.
            centroid: Cluster center values.
            silhouette: Silhouette coefficient.
            characteristics: Cluster characteristics.

        Returns:
            ClusterDTO representation.
        """
        return ClusterDTO(
            cluster_id=cluster_id,
            places=place_ids,
            centroid=centroid,
            silhouette_score=silhouette,
            characteristics=characteristics,
        )

    @staticmethod
    def pattern_to_dto(
        pattern_id: int,
        keyword: str,
        frequency: int,
        first_seen: datetime,
        last_seen: Optional[datetime],
        sentiment_correlation: float,
        affected_places: Optional[List[int]] = None,
    ) -> PatternDTO:
        """Transform pattern data to DTO.

        Args:
            pattern_id: Unique pattern ID.
            keyword: Pattern keyword/phrase.
            frequency: How often pattern appears.
            first_seen: When first detected.
            last_seen: When last detected.
            sentiment_correlation: Correlation to sentiment.
            affected_places: Places with pattern.

        Returns:
            PatternDTO representation.
        """
        return PatternDTO(
            pattern_id=pattern_id,
            keyword=keyword,
            frequency=frequency,
            first_seen=first_seen,
            last_seen=last_seen,
            sentiment_correlation=sentiment_correlation,
            affected_places=affected_places or [],
        )

    @staticmethod
    def analytics_run_to_dto(
        run_id: int,
        place_ids: List[int],
        analysis_types: List[str],
        status: str,
        started_at: datetime,
        completed_at: Optional[datetime],
        results_summary: Optional[Dict[str, Any]] = None,
    ) -> AnalyticsRunDTO:
        """Transform analytics run data to DTO.

        Args:
            run_id: Unique run ID.
            place_ids: Places analyzed.
            analysis_types: Types of analyses.
            status: Current status.
            started_at: When run started.
            completed_at: When run completed.
            results_summary: Summary of results.

        Returns:
            AnalyticsRunDTO representation.
        """
        duration = None
        if completed_at:
            duration = int((completed_at - started_at).total_seconds())

        return AnalyticsRunDTO(
            run_id=run_id,
            place_ids=place_ids,
            analysis_types=analysis_types,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            results_summary=results_summary or {},
        )

    @staticmethod
    def comparison_to_dto(
        current_value: float,
        previous_value: float,
    ) -> ComparisonResultDTO:
        """Transform comparison data to DTO.

        Args:
            current_value: Current/new value.
            previous_value: Previous/baseline value.

        Returns:
            ComparisonResultDTO representation.
        """
        absolute_change = current_value - previous_value
        percent_change = (
            ((absolute_change) / abs(previous_value) * 100)
            if previous_value != 0 else 0.0
        )

        if abs(absolute_change) < 0.01:
            direction = "stable"
        elif absolute_change > 0:
            direction = "increase"
        else:
            direction = "decrease"

        # Simple significance test: > 5% change
        is_significant = abs(percent_change) >= 5.0

        return ComparisonResultDTO(
            current_value=current_value,
            previous_value=previous_value,
            absolute_change=absolute_change,
            percent_change=percent_change,
            direction=direction,
            is_significant=is_significant,
        )

    @staticmethod
    def statistics_to_dto(
        values: List[float],
    ) -> SummaryStatisticsDTO:
        """Transform list of values to statistics DTO.

        Args:
            values: List of numeric values.

        Returns:
            SummaryStatisticsDTO with statistics calculated.
        """
        if not values:
            return SummaryStatisticsDTO(
                count=0, mean=0, median=0, std_dev=0,
                min_value=0, max_value=0, percentile_25=0, percentile_75=0,
            )

        sorted_vals = sorted(values)
        count = len(sorted_vals)
        mean = sum(sorted_vals) / count
        median = sorted_vals[count // 2]

        # Calculate standard deviation
        variance = sum((x - mean) ** 2 for x in sorted_vals) / count
        std_dev = variance ** 0.5

        # Calculate percentiles
        p25_idx = int(count * 0.25)
        p75_idx = int(count * 0.75)

        return SummaryStatisticsDTO(
            count=count,
            mean=mean,
            median=median,
            std_dev=std_dev,
            min_value=min(sorted_vals),
            max_value=max(sorted_vals),
            percentile_25=sorted_vals[p25_idx],
            percentile_75=sorted_vals[p75_idx],
        )

    @staticmethod
    def cache_entry_to_dto(
        cache_key: str,
        entity_type: str,
        entity_id: int,
        cached_value: Dict[str, Any],
        created_at: datetime,
        expires_at: datetime,
    ) -> CacheEntryDTO:
        """Transform cache entry to DTO.

        Args:
            cache_key: Cache lookup key.
            entity_type: Type of cached entity.
            entity_id: Entity ID.
            cached_value: The cached data.
            created_at: When cached.
            expires_at: When cache expires.

        Returns:
            CacheEntryDTO representation.
        """
        return CacheEntryDTO(
            cache_key=cache_key,
            entity_type=entity_type,
            entity_id=entity_id,
            cached_value=cached_value,
            created_at=created_at,
            expires_at=expires_at,
        )


__all__ = ["DTOTransformer"]
