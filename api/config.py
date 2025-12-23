"""FastAPI Configuration Module"""
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # App
    app_name: str = "Analytics API"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://localhost/analytics")
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # API
    api_title: str = "Analytics Service API"
    api_description: str = "REST API for analytics services (NLP, Prediction, Correlation, Clustering, Pattern Detection)"
    api_version: str = "1.0.0"
    
    # CORS
    cors_origins: list = ["*"]
    cors_credentials: bool = True
    cors_methods: list = ["*"]
    cors_headers: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
