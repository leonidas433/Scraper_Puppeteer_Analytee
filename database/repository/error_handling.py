"""
Database repository error handling.

Provides custom exceptions for repository operations with context-aware
error information and automatic logging.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RepositoryException(Exception):
    """Base exception for all repository-level errors."""

    def __init__(
        self,
        message: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize repository exception.

        Args:
            message: Error description
            entity_type: Type of entity being operated on
            entity_id: ID of entity that caused the error
            context: Additional context dict
        """
        self.message = message
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.context = context or {}
        self.timestamp = datetime.utcnow()

        # Build full message
        full_msg = self.message
        if entity_type:
            full_msg += f" (Entity: {entity_type}"
            if entity_id:
                full_msg += f"#{entity_id}"
            full_msg += ")"

        super().__init__(full_msg)

        # Log with context
        logger.error(
            f"{self.__class__.__name__}: {full_msg}",
            extra={
                "entity_type": entity_type,
                "entity_id": entity_id,
                "context": context,
            },
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dict for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }


class EntityNotFound(RepositoryException):
    """Raised when entity query returns no results."""

    pass


class DuplicateEntity(RepositoryException):
    """Raised when creating duplicate entity with unique constraint."""

    pass


class TransactionFailed(RepositoryException):
    """Raised when transaction fails and rolls back."""

    pass


class IntegrityViolation(RepositoryException):
    """Raised when database integrity constraint is violated."""

    pass


class InvalidQuery(RepositoryException):
    """Raised when query is malformed or invalid."""

    pass


class SpecificationError(RepositoryException):
    """Raised when specification building fails."""

    pass


class ConnectionPoolError(RepositoryException):
    """Raised when connection pool fails."""

    pass


def handle_db_error(exc: Exception, entity_type: Optional[str] = None) -> RepositoryException:
    """Convert SQLAlchemy exceptions to repository exceptions.

    Args:
        exc: SQLAlchemy exception
        entity_type: Type of entity being operated on

    Returns:
        Corresponding RepositoryException
    """
    exc_str = str(exc)
    exc_type = type(exc).__name__

    # Check for specific SQLAlchemy errors
    if "IntegrityError" in exc_type or "unique constraint" in exc_str.lower():
        return DuplicateEntity(
            f"Duplicate entity: {exc_str}",
            entity_type=entity_type,
            context={"original_error": exc_type},
        )

    if "NoResultFound" in exc_type or "no rows were found" in exc_str.lower():
        return EntityNotFound(
            "Entity not found",
            entity_type=entity_type,
            context={"original_error": exc_type},
        )

    if "OperationalError" in exc_type or "connection" in exc_str.lower():
        return ConnectionPoolError(
            f"Database connection error: {exc_str}",
            entity_type=entity_type,
            context={"original_error": exc_type},
        )

    # Generic database error
    return TransactionFailed(
        f"Database transaction failed: {exc_str}",
        entity_type=entity_type,
        context={"original_error": exc_type},
    )
