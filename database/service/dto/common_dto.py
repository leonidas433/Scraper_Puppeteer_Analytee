"""Common Data Transfer Objects used across services.

Shared DTOs that appear in multiple service responses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List


@dataclass
class InsightsDTO:
    """Key insight from analysis.

    Attributes:
        insight_id: Unique insight identifier.
        category: Category of insight.
        description: Detailed insight description.
        confidence: Confidence level (0-1).
        impact: Estimated business impact.
        recommended_action: Suggested action based on insight.
    """

    insight_id: int
    category: str
    description: str
    confidence: float
    impact: str
    recommended_action: Optional[str] = None


@dataclass
class TimeSeriesDataDTO:
    """Time series data for a metric over time.

    Attributes:
        metric_name: Name of the metric.
        data_points: List of (timestamp, value) tuples.
        aggregation: How data is aggregated ('daily', 'weekly', etc).
        unit: Unit of measurement.
    """

    metric_name: str
    data_points: List[tuple[datetime, float]] = field(default_factory=list)
    aggregation: str = "daily"
    unit: str = ""

    def add_point(self, timestamp: datetime, value: float) -> None:
        """Add a data point to the time series.

        Args:
            timestamp: When this measurement was taken.
            value: The measured value.
        """
        self.data_points.append((timestamp, value))

    def get_latest_value(self) -> Optional[float]:
        """Get the most recent value in time series.

        Returns:
            The latest value, or None if empty.
        """
        if self.data_points:
            return self.data_points[-1][1]
        return None


@dataclass
class SummaryStatisticsDTO:
    """Statistical summary of a dataset.

    Attributes:
        count: Number of values.
        mean: Average value.
        median: Middle value.
        std_dev: Standard deviation.
        min_value: Minimum value.
        max_value: Maximum value.
        percentile_25: 25th percentile.
        percentile_75: 75th percentile.
    """

    count: int
    mean: float
    median: float
    std_dev: float
    min_value: float
    max_value: float
    percentile_25: float
    percentile_75: float

    def get_range(self) -> float:
        """Get range (max - min).

        Returns:
            The range of values.
        """
        return self.max_value - self.min_value

    def get_iqr(self) -> float:
        """Get inter-quartile range.

        Returns:
            The IQR (75th percentile - 25th percentile).
        """
        return self.percentile_75 - self.percentile_25


@dataclass
class ComparisonResultDTO:
    """Result of comparing two values or periods.

    Attributes:
        current_value: Current/new value.
        previous_value: Previous/baseline value.
        absolute_change: Absolute difference.
        percent_change: Percentage change.
        direction: Direction of change ('increase', 'decrease', 'stable').
        is_significant: Whether change is statistically significant.
    """

    current_value: float
    previous_value: float
    absolute_change: float
    percent_change: float
    direction: str
    is_significant: bool


@dataclass
class RankingItemDTO:
    """Single item in a ranking result.

    Attributes:
        rank: Position in ranking (1-indexed).
        entity_id: ID of ranked entity.
        entity_name: Name of ranked entity.
        score: Score used for ranking.
        percentile: Percentile position (0-100).
    """

    rank: int
    entity_id: int
    entity_name: str
    score: float
    percentile: float


@dataclass
class DistributionBinDTO:
    """Single bin in a distribution histogram.

    Attributes:
        bin_label: Label for this bin.
        count: Number of items in this bin.
        percent: Percentage of total.
        lower_bound: Lower bound of bin.
        upper_bound: Upper bound of bin.
    """

    bin_label: str
    count: int
    percent: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


@dataclass
class ReportDTO:
    """Complete analysis report.

    Attributes:
        report_id: Unique report identifier.
        report_type: Type of report.
        generated_at: When report was generated.
        period_start: Start of analysis period.
        period_end: End of analysis period.
        sections: Report sections with content.
        metadata: Additional metadata.
    """

    report_id: int
    report_type: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    sections: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_section(self, section_name: str, content: str) -> None:
        """Add a section to the report.

        Args:
            section_name: Name of the section.
            content: Section content/text.
        """
        self.sections[section_name] = content


@dataclass
class BenchmarkResultDTO:
    """Result of benchmarking against peers.

    Attributes:
        entity_id: Entity being benchmarked.
        entity_name: Name of entity.
        metric_name: Metric being benchmarked.
        entity_value: This entity's value.
        peer_average: Average value of peers.
        peer_median: Median value of peers.
        percentile: Percentile rank (0-100).
        status: Performance status vs peers.
    """

    entity_id: int
    entity_name: str
    metric_name: str
    entity_value: float
    peer_average: float
    peer_median: float
    percentile: float
    status: str


@dataclass
class AlertDTO:
    """Alert about critical condition.

    Attributes:
        alert_id: Unique alert ID.
        severity: Severity level (critical, high, medium, low).
        title: Alert title.
        message: Detailed message.
        affected_entity: Entity this alert concerns.
        triggered_at: When alert was triggered.
        requires_action: Whether action is required.
    """

    alert_id: int
    severity: str
    title: str
    message: str
    affected_entity: str
    triggered_at: datetime
    requires_action: bool = False


__all__ = [
    "InsightsDTO",
    "TimeSeriesDataDTO",
    "SummaryStatisticsDTO",
    "ComparisonResultDTO",
    "RankingItemDTO",
    "DistributionBinDTO",
    "ReportDTO",
    "BenchmarkResultDTO",
    "AlertDTO",
]
