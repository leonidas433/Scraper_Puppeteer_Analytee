"""FastAPI main application module - Entry point for API"""
from api.v1 import create_app
from api.v1.routers import (
    health_router,
    nlp_router,
    prediction_router,
    correlation_router,
    clustering_router,
    pattern_router
)
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = create_app()

# Register routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(nlp_router, prefix="/api/v1")
app.include_router(prediction_router, prefix="/api/v1")
app.include_router(correlation_router, prefix="/api/v1")
app.include_router(clustering_router, prefix="/api/v1")
app.include_router(pattern_router, prefix="/api/v1")

logger.info("FastAPI application initialized with all routers")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
