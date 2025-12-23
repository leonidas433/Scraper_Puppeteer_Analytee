"""Response Data Transfer Objects for service layer.

DTOs that represent data returned from service methods to clients.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class TrendDTO:
    """Represents a trend in data over time.

    Attributes:
        direction: Trend direction ('up', 'down', 'stable').
        strength: Strength of trend (0.0 to 1.0).
        start_value: Value at start of trend period.
        end_value: Value at end of trend period.
        change_percent: Percentage change.
    """

    direction: str
    strength: float
    start_value: float
    end_value: float
    change_percent: float


@dataclass
class AnomalyDTO:
    """Represents a detected anomaly in data.

    Attributes:
        anomaly_id: Unique identifier for anomaly.
        timestamp: When anomaly was detected.
        value: The anomalous value.
        expected_range: Expected normal range.
        severity: Severity level (1-5).
        description: Human-readable description.
    """

    anomaly_id: int
    timestamp: datetime
    value: float
    expected_range: tuple[float, float]
    severity: int
    description: str


@dataclass
class SpikeDTO:
    """Represents a sudden spike or dip in data.

    Attributes:
        spike_timestamp: When spike occurred.
        spike_value: Peak/trough value.
        pre_spike_average: Average before spike.
        spike_magnitude: Magnitude of spike.
        recovery_time: Time to return to normal (in hours).
    """

    spike_timestamp: datetime
    spike_value: float
    pre_spike_average: float
    spike_magnitude: float
    recovery_time: Optional[int]


@dataclass
class PerformanceMetricsDTO:
    """Aggregated performance metrics.

    Attributes:
        metric_name: Name of metric.
        current_value: Current value.
        target_value: Target value.
        performance_percent: Achievement percentage.
        status: Status ('green', 'yellow', 'red').
    """

    metric_name: str
    current_value: float
    target_value: float
    performance_percent: float
    status: str


@dataclass
class NLPResultDTO:
    """Results from NLP analysis.

    Attributes:
        analysis_id: Unique analysis ID.
        place_id: Place analyzed.
        overall_sentiment: Overall sentiment score (-1 to 1).
        emotion_scores: Distribution of emotions detected.
        key_insights: Top insights from reviews.
        sentiment_trend: Trend in sentiment over time.
        anomalies: Detected sentiment anomalies.
    """

    analysis_id: int
    place_id: int
    overall_sentiment: float
    emotion_scores: Dict[str, float]
    key_insights: List[str]
    sentiment_trend: Optional[TrendDTO]
    anomalies: List[AnomalyDTO] = field(default_factory=list)


@dataclass
class ForecastDTO:
    """Prediction forecast for future period.

    Attributes:
        metric_name: What is being forecasted.
        forecast_values: Predicted values for each period.
        confidence_intervals: Confidence bounds for predictions.
        trend: Overall trend direction.
        model_r_squared: R-squared of prediction model.
    """

    metric_name: str
    forecast_values: List[float]
    confidence_intervals: List[tuple[float, float]]
    trend: str
    model_r_squared: float


@dataclass
class CorrelationResultDTO:
    """Correlation analysis results.

    Attributes:
        source_metric: First metric in correlation.
        target_metric: Second metric in correlation.
        correlation_coefficient: Pearson correlation (-1 to 1).
        p_value: Statistical significance p-value.
        lag_days: Optimal lag in days (if lagged correlation).
        interpretation: Human-readable interpretation.
    """

    source_metric: str
    target_metric: str
    correlation_coefficient: float
    p_value: float
    lag_days: int
    interpretation: str


@dataclass
class ClusterDTO:
    """Cluster assignment for places.

    Attributes:
        cluster_id: Unique cluster ID.
        places: List of place IDs in cluster.
        centroid: Cluster center characteristics.
        silhouette_score: Cluster quality score (0-1).
        characteristics: Defining characteristics of cluster.
    """

    cluster_id: int
    places: List[int]
    centroid: Dict[str, float]
    silhouette_score: float
    characteristics: Dict[str, str]


@dataclass
class PatternDTO:
    """Detected pattern in review data.

    Attributes:
        pattern_id: Unique pattern ID.
        keyword: Pattern keyword or phrase.
        frequency: How often pattern appears.
        first_seen: When pattern first appeared.
        last_seen: When pattern last appeared.
        sentiment_correlation: How pattern correlates to sentiment.
        affected_places: Places where pattern appears.
    """

    pattern_id: int
    keyword: str
    frequency: int
    first_seen: datetime
    last_seen: Optional[datetime]
    sentiment_correlation: float
    affected_places: List[int] = field(default_factory=list)


@dataclass
class AnalyticsRunDTO:
    """Represents an analytics pipeline run.

    Attributes:
        run_id: Unique run ID.
        place_ids: Places analyzed.
        analysis_types: Types of analyses run.
        status: Current status.
        started_at: When run started.
        completed_at: When run completed.
        duration_seconds: Total runtime in seconds.
        results_summary: Summary of results.
    """

    run_id: int
    place_ids: List[int]
    analysis_types: List[str]
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    results_summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutiveSummaryDTO:
    """High-level summary of analytics for executives.

    Attributes:
        summary_id: Unique summary ID.
        generated_at: When summary was generated.
        period: Time period covered.
        total_places: Number of places analyzed.
        key_metrics: Most important KPIs.
        top_opportunities: Highest priority actions.
        risks: Critical issues requiring attention.
    """

    summary_id: int
    generated_at: datetime
    period: str
    total_places: int
    key_metrics: Dict[str, float]
    top_opportunities: List[str]
    risks: List[str]


@dataclass
class KPIResultDTO:
    """KPI calculation results.

    Attributes:
        kpi_id: Unique KPI ID.
        place_id: Place the KPI applies to.
        period: Reporting period.
        metric_values: Calculated KPI values.
        comparisons: Comparison to previous period.
        status: Status indicator (green/yellow/red).
    """

    kpi_id: int
    place_id: int
    period: str
    metric_values: Dict[str, float]
    comparisons: Dict[str, float]
    status: str


@dataclass
class CacheEntryDTO:
    """Represents a cached analysis result.

    Attributes:
        cache_key: Cache lookup key.
        entity_type: Type of entity cached.
        entity_id: ID of entity.
        cached_value: The cached data.
        created_at: When cache entry was created.
        expires_at: When cache entry expires.
    """

    cache_key: str
    entity_type: str
    entity_id: int
    cached_value: Dict[str, Any]
    created_at: datetime
    expires_at: datetime


@dataclass
class ErrorResponseDTO:
    """Standard error response format.

    Attributes:
        error_code: Machine-readable error code.
        error_message: Human-readable message.
        details: Additional error details.
        timestamp: When error occurred.
    """

    error_code: str
    error_message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


__all__ = [
    "TrendDTO",
    "AnomalyDTO",
    "SpikeDTO",
    "PerformanceMetricsDTO",
    "NLPResultDTO",
    "ForecastDTO",
    "CorrelationResultDTO",
    "ClusterDTO",
    "PatternDTO",
    "AnalyticsRunDTO",
    "ExecutiveSummaryDTO",
    "KPIResultDTO",
    "CacheEntryDTO",
    "ErrorResponseDTO",
]
