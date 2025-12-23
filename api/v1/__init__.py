"""FastAPI application factory"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from api.config import settings
from api.v1.middleware.error_handler import (
    global_exception_handler,
    validation_exception_handler,
    not_found_handler
)


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        debug=settings.debug
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
    )
    
    # Add exception handlers
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    return app
