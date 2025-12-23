"""Service layer package for domain services.

Provides:
- BaseService: Abstract base class for all services
- Validation Framework: 4-layer validation (Input, Domain, CrossEntity, BusinessRule)
- DTOs: Request, Response, and Common data transfer objects
"""

from database.service.base import (
    BaseService,
    ServiceException,
    ValidationException,
    CacheEntry,
)
from database.service.validation import (
    InputValidator,
    DomainValidator,
    CrossEntityValidator,
    BusinessRuleValidator,
)
from database.service.dto import (
    # Request DTOs
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
    # Response DTOs
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
    # Common DTOs
    InsightsDTO,
    TimeSeriesDataDTO,
    SummaryStatisticsDTO,
    ComparisonResultDTO,
    RankingItemDTO,
    DistributionBinDTO,
    ReportDTO,
    BenchmarkResultDTO,
    AlertDTO,
    # Transformers
    DTOTransformer,
)

__version__ = "1.0.0"

__all__ = [
    # Base service
    "BaseService",
    "ServiceException",
    "ValidationException",
    "CacheEntry",
    # Validators
    "InputValidator",
    "DomainValidator",
    "CrossEntityValidator",
    "BusinessRuleValidator",
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
