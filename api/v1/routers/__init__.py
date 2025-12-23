"""API v1 routers"""
from .health import router as health_router
from .nlp import router as nlp_router
from .prediction import router as prediction_router
from .correlation import router as correlation_router
from .clustering import router as clustering_router
from .pattern_detection import router as pattern_router

__all__ = [
    "health_router",
    "nlp_router",
    "prediction_router",
    "correlation_router",
    "clustering_router",
    "pattern_router"
]
