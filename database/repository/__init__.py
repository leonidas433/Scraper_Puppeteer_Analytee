"""
Repository Package - Data Access Layer

Provides domain-specific repository classes for all entities with:
- CRUD operations via BaseRepository
- Domain-specific queries
- Automatic transaction management
- Comprehensive error handling
- Audit logging

Core Infrastructure:
- error_handling: Custom exception hierarchy
- logging_config: Audit and performance logging
- database_config: Multi-database configuration
- base: Generic BaseRepository[T] template
- unit_of_work: Transaction context manager

Phase 1 Repositories (Ingestion):
- place_repository: Location/business queries
- review_repository: Review data analysis
- kpi_repository: Temporal KPI aggregation
- cache_repository: Performance caching

Phase 2 Repositories (Analytics):
- nlp_repository: Sentiment/context analysis
- prediction_repository: Forecast queries
- correlation_repository: Factor driver analysis
- cluster_repository: Cohort similarity
- pattern_repository: Behavioral patterns
- analytics_run_repository: Pipeline execution tracking
"""

# Error Handling
from .error_handling import (
    RepositoryException,
    EntityNotFound,
    DuplicateEntity,
    TransactionFailed,
    IntegrityViolation,
    InvalidQuery,
    SpecificationError,
    ConnectionPoolError,
    handle_db_error,
)

# Logging
from .logging_config import (
    AuditFormatter,
    AuditLog,
    setup_audit_logging,
    log_crud_operation,
    log_query_execution,
    log_transaction,
)

# Database Configuration
from .database_config import (
    DatabaseConfig,
    get_session_factory,
    reset_session_factory,
    get_session,
)

# Base Repository
from .base import BaseRepository

# Unit of Work
from .unit_of_work import UnitOfWork

# Phase 1 Repositories
from .place_repository import PlaceRepository
from .review_repository import ReviewRepository
from .kpi_repository import KPIRepository
from .cache_repository import CacheRepository

# Phase 2 Repositories
from .nlp_repository import NLPRepository
from .prediction_repository import PredictionRepository
from .correlation_repository import CorrelationRepository
from .cluster_repository import ClusterRepository
from .pattern_repository import PatternRepository
from .analytics_run_repository import AnalyticsRunRepository

__all__ = [
    # Exceptions
    "RepositoryException",
    "EntityNotFound",
    "DuplicateEntity",
    "TransactionFailed",
    "IntegrityViolation",
    "InvalidQuery",
    "SpecificationError",
    "ConnectionPoolError",
    "handle_db_error",
    # Logging
    "AuditFormatter",
    "AuditLog",
    "setup_audit_logging",
    "log_crud_operation",
    "log_query_execution",
    "log_transaction",
    # Database
    "DatabaseConfig",
    "get_session_factory",
    "reset_session_factory",
    "get_session",
    # Base
    "BaseRepository",
    # Unit of Work
    "UnitOfWork",
    # Phase 1 Repositories
    "PlaceRepository",
    "ReviewRepository",
    "KPIRepository",
    "CacheRepository",
    # Phase 2 Repositories
    "NLPRepository",
    "PredictionRepository",
    "CorrelationRepository",
    "ClusterRepository",
    "PatternRepository",
    "AnalyticsRunRepository",
]
