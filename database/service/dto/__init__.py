"""Data Transfer Objects package for service layer.

Provides request DTOs (input), response DTOs (output), common DTOs (shared),
and transformers for converting between models and DTOs.
"""

from database.service.dto.request_dto import (
    DateRangeDTO,
    ReviewBatchDTO,
    AnalyticsConfigDTO,
    NLPAnalysisRequestDTO,
    PredictionRequestDTO,
    ClusteringRequestDTO,
    PatternDetectionRequestDTO,
    KPICalculationRequestDTO,
    FilterDTO,
    PaginationDTO,
    SortDTO,
)
from database.service.dto.response_dto import (
    TrendDTO,
    AnomalyDTO,
    SpikeDTO,
    PerformanceMetricsDTO,
    NLPResultDTO,
    ForecastDTO,
    CorrelationResultDTO,
    ClusterDTO,
    PatternDTO,
    AnalyticsRunDTO,
    ExecutiveSummaryDTO,
    KPIResultDTO,
    CacheEntryDTO,
    ErrorResponseDTO,
)
from database.service.dto.common_dto import (
    InsightsDTO,
    TimeSeriesDataDTO,
    SummaryStatisticsDTO,
    ComparisonResultDTO,
    RankingItemDTO,
    DistributionBinDTO,
    ReportDTO,
    BenchmarkResultDTO,
    AlertDTO,
)
from database.service.dto.transformers import DTOTransformer

__all__ = [
    # Request DTOs
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
    # Response DTOs
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
    # Common DTOs
    "InsightsDTO",
    "TimeSeriesDataDTO",
    "SummaryStatisticsDTO",
    "ComparisonResultDTO",
    "RankingItemDTO",
    "DistributionBinDTO",
    "ReportDTO",
    "BenchmarkResultDTO",
    "AlertDTO",
    # Transformers
    "DTOTransformer",
]
