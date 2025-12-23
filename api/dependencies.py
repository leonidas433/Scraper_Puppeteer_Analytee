"""FastAPI Dependencies - Dependency Injection for services"""
from functools import lru_cache
from database.repository.unit_of_work import UnitOfWork
from database.service.analytics import (
    NLPService,
    PredictionService,
    CorrelationService,
    ClusteringService,
    PatternDetectionService
)

# Global instances (cached)
_uow_instance = None
_nlp_service_instance = None
_prediction_service_instance = None
_correlation_service_instance = None
_clustering_service_instance = None
_pattern_service_instance = None


def get_uow() -> UnitOfWork:
    """Get or create UnitOfWork instance"""
    global _uow_instance
    if _uow_instance is None:
        _uow_instance = UnitOfWork()
    return _uow_instance


def get_nlp_service() -> NLPService:
    """Get or create NLPService instance"""
    global _nlp_service_instance
    if _nlp_service_instance is None:
        _nlp_service_instance = NLPService(get_uow())
    return _nlp_service_instance


def get_prediction_service() -> PredictionService:
    """Get or create PredictionService instance"""
    global _prediction_service_instance
    if _prediction_service_instance is None:
        _prediction_service_instance = PredictionService(get_uow())
    return _prediction_service_instance


def get_correlation_service() -> CorrelationService:
    """Get or create CorrelationService instance"""
    global _correlation_service_instance
    if _correlation_service_instance is None:
        _correlation_service_instance = CorrelationService(get_uow())
    return _correlation_service_instance


def get_clustering_service() -> ClusteringService:
    """Get or create ClusteringService instance"""
    global _clustering_service_instance
    if _clustering_service_instance is None:
        _clustering_service_instance = ClusteringService(get_uow())
    return _clustering_service_instance


def get_pattern_service() -> PatternDetectionService:
    """Get or create PatternDetectionService instance"""
    global _pattern_service_instance
    if _pattern_service_instance is None:
        _pattern_service_instance = PatternDetectionService(get_uow())
    return _pattern_service_instance
