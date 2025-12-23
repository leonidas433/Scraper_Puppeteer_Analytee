"""Request Data Transfer Objects for service layer.

DTOs that represent incoming requests to service methods, with validation
and transformation logic.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Dict, Any


@dataclass
class DateRangeDTO:
    """Represents a date range for time-based queries.

    Attributes:
        start_date: Start date (inclusive).
        end_date: End date (inclusive).
    """

    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        """Validate date range after initialization."""
        if self.end_date < self.start_date:
            raise ValueError(
                f"end_date ({self.end_date}) before "
                f"start_date ({self.start_date})"
            )

    def get_days_count(self) -> int:
        """Get number of days in range (inclusive).

        Returns:
            Number of days from start to end (inclusive).
        """
        return (self.end_date - self.start_date).days + 1


@dataclass
class ReviewBatchDTO:
    """Request DTO for batch review processing.

    Attributes:
        place_id: ID of the place these reviews belong to.
        reviews: List of review data as dictionaries.
    """

    place_id: int
    reviews: List[Dict[str, Any]] = field(default_factory=list)

    def get_review_count(self) -> int:
        """Get count of reviews in batch.

        Returns:
            Number of reviews in batch.
        """
        return len(self.reviews)

    def is_empty(self) -> bool:
        """Check if batch has no reviews.

        Returns:
            True if batch is empty, False otherwise.
        """
        return len(self.reviews) == 0


@dataclass
class AnalyticsConfigDTO:
    """Configuration for analytics pipeline execution.

    Attributes:
        place_ids: IDs of places to analyze.
        analysis_types: Types of analyses to run.
        date_range: Date range for analysis.
        run_in_parallel: Whether to run analyses in parallel.
        include_cache: Whether to use cached results if available.
    """

    place_ids: List[int]
    analysis_types: List[str] = field(default_factory=list)
    date_range: Optional[DateRangeDTO] = None
    run_in_parallel: bool = True
    include_cache: bool = True

    def add_analysis_type(self, analysis_type: str) -> None:
        """Add an analysis type to the config.

        Args:
            analysis_type: Type of analysis to add.
        """
        if analysis_type not in self.analysis_types:
            self.analysis_types.append(analysis_type)

    def set_date_range(
        self,
        start_date: date,
        end_date: date,
    ) -> None:
        """Set the date range for analysis.

        Args:
            start_date: Start date.
            end_date: End date.
        """
        self.date_range = DateRangeDTO(start_date, end_date)


@dataclass
class NLPAnalysisRequestDTO:
    """Request DTO for NLP analysis.

    Attributes:
        place_id: Place to analyze.
        include_trajectory: Include emotional trajectory analysis.
        include_anomalies: Include anomaly detection.
        include_trends: Include trend analysis.
    """

    place_id: int
    include_trajectory: bool = True
    include_anomalies: bool = True
    include_trends: bool = True


@dataclass
class PredictionRequestDTO:
    """Request DTO for predictive analysis.

    Attributes:
        place_id: Place to forecast.
        forecast_days: Number of days to forecast.
        confidence_level: Confidence level for predictions.
    """

    place_id: int
    forecast_days: int = 30
    confidence_level: float = 0.95


@dataclass
class ClusteringRequestDTO:
    """Request DTO for clustering analysis.

    Attributes:
        place_ids: Places to cluster.
        k_clusters: Number of clusters (K in K-means).
        recalculate: Force recalculation even if cached.
    """

    place_ids: List[int]
    k_clusters: int = 5
    recalculate: bool = False


@dataclass
class PatternDetectionRequestDTO:
    """Request DTO for pattern detection.

    Attributes:
        place_id: Place to analyze.
        min_frequency: Minimum pattern occurrences.
        include_temporal: Include temporal patterns.
        include_behavioral: Include behavioral anomalies.
    """

    place_id: int
    min_frequency: int = 2
    include_temporal: bool = True
    include_behavioral: bool = True


@dataclass
class KPICalculationRequestDTO:
    """Request DTO for KPI calculation.

    Attributes:
        place_ids: Places to calculate KPIs for.
        period: Aggregation period ('daily', 'weekly', 'monthly').
        date_range: Date range for KPI calculation.
    """

    place_ids: List[int]
    period: str = "daily"
    date_range: Optional[DateRangeDTO] = None


@dataclass
class FilterDTO:
    """Generic filter criteria for queries.

    Attributes:
        field: Field name to filter on.
        operator: Comparison operator.
        value: Filter value.
    """

    field: str
    operator: str  # 'eq', 'lt', 'gt', 'lte', 'gte', 'in', 'contains'
    value: Any


@dataclass
class PaginationDTO:
    """Pagination parameters for result sets.

    Attributes:
        page: Page number (1-indexed).
        page_size: Items per page.
    """

    page: int = 1
    page_size: int = 50

    def get_offset(self) -> int:
        """Calculate offset for query.

        Returns:
            Offset value for database query.
        """
        return (self.page - 1) * self.page_size

    def get_limit(self) -> int:
        """Get limit for query.

        Returns:
            Limit value for database query.
        """
        return self.page_size


@dataclass
class SortDTO:
    """Sorting specification for result sets.

    Attributes:
        field: Field name to sort on.
        ascending: Sort direction (True=ascending, False=descending).
    """

    field: str
    ascending: bool = True

    def get_order_by(self) -> str:
        """Get SQL ORDER BY clause.

        Returns:
            SQL order by specification.
        """
        direction = "ASC" if self.ascending else "DESC"
        return f"{self.field} {direction}"


__all__ = [
    "DateRangeDTO",
    "ReviewBatchDTO",
    "AnalyticsConfigDTO",
    "NLPAnalysisRequestDTO",
    "PredictionRequestDTO",
    "ClusteringRequestDTO",
    "PatternDetectionRequestDTO",
    "KPICalculationRequestDTO",
    "FilterDTO",
    "PaginationDTO",
    "SortDTO",
]
