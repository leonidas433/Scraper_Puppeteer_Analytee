"""Base service class for all domain services.

This module provides the abstract base class that all domain services inherit
from, implementing common functionality for transaction management, logging,
error handling, and caching.

Attributes:
    BaseService: Abstract base class for domain services providing standard
        transaction and cache management patterns.
"""

import logging
from abc import ABC
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, TypeVar, Generic
from contextlib import contextmanager

from database.repository.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceException(Exception):
    """Base exception for service layer errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "SERVICE_ERROR",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize service exception.

        Args:
            message: Human-readable error message.
            error_code: Machine-readable error code for client handling.
            context: Additional context data (entity IDs, etc.).
        """
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.timestamp = datetime.utcnow().isoformat()
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/responses.

        Returns:
            Dictionary representation of exception with all metadata.
        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp,
        }


class ValidationException(ServiceException):
    """Raised when validation fails at any layer."""

    def __init__(
        self,
        message: str,
        field: str = "",
        value: Any = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize validation exception.

        Args:
            message: Description of validation failure.
            field: Name of field that failed validation.
            value: The value that failed validation.
            context: Additional validation context.
        """
        self.field = field
        self.value = value
        error_context = context or {}
        error_context.update({"field": field, "failed_value": str(value)})
        super().__init__(
            message, error_code="VALIDATION_ERROR", context=error_context
        )


class CacheEntry(Generic[T]):
    """Generic cache entry with TTL management.

    Attributes:
        value: The cached value of generic type T.
        created_at: Timestamp when entry was created.
        ttl_seconds: Time-to-live in seconds.
    """

    def __init__(self, value: T, ttl_seconds: int = 3600) -> None:
        """Initialize cache entry.

        Args:
            value: The value to cache.
            ttl_seconds: Time-to-live in seconds (default: 3600).
        """
        self.value: T = value
        self.created_at: datetime = datetime.utcnow()
        self.ttl_seconds: int = ttl_seconds

    def is_expired(self) -> bool:
        """Check if cache entry has expired.

        Returns:
            True if entry has exceeded TTL, False otherwise.
        """
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow() > expiry_time

    def get_value(self) -> Optional[T]:
        """Get cached value if not expired.

        Returns:
            The cached value if still valid, None if expired.
        """
        if self.is_expired():
            return None
        return self.value


class BaseService(ABC):
    """Abstract base class for all domain services.

    Provides common functionality including transaction management, logging,
    error handling, and in-memory caching with TTL support.

    Attributes:
        unit_of_work: UnitOfWork instance for transaction management.
        _cache: In-memory cache for results (shared across all service).
        _cache_stats: Statistics about cache hits/misses.
    """

    # Class-level shared cache across all service instances
    _cache: Dict[str, CacheEntry[Any]] = {}
    _cache_stats: Dict[str, int] = {"hits": 0, "misses": 0, "invalidations": 0}

    def __init__(self, unit_of_work: UnitOfWork) -> None:
        """Initialize base service.

        Args:
            unit_of_work: UnitOfWork instance for transaction management.

        Raises:
            ValueError: If unit_of_work is None.
        """
        if unit_of_work is None:
            raise ValueError("unit_of_work cannot be None")
        self.unit_of_work = unit_of_work
        self.logger = logging.getLogger(self.__class__.__name__)

    def _generate_cache_key(self, *args: Any, **kwargs: Any) -> str:
        """Generate a cache key from method arguments.

        This creates a deterministic string key from positional and keyword
        arguments. Used to identify unique cache entries for methods.

        Args:
            *args: Positional arguments to include in key.
            **kwargs: Keyword arguments to include in key.

        Returns:
            A cache key string combining class name, args, and kwargs.
        """
        # Create key from class name, args, and sorted kwargs
        args_str = "|".join(str(arg) for arg in args)
        kwargs_str = "|".join(
            f"{k}={v}" for k, v in sorted(kwargs.items())
        )
        parts = [self.__class__.__name__]
        if args_str:
            parts.append(args_str)
        if kwargs_str:
            parts.append(kwargs_str)
        return ":".join(parts)

    def _get_cached_value(self, cache_key: str) -> Optional[Any]:
        """Retrieve value from cache if exists and not expired.

        Args:
            cache_key: The cache key to look up.

        Returns:
            The cached value if found and valid, None otherwise.
        """
        if cache_key not in self._cache:
            BaseService._cache_stats["misses"] += 1
            return None

        entry = self._cache[cache_key]
        if entry.is_expired():
            del self._cache[cache_key]
            BaseService._cache_stats["misses"] += 1
            return None

        BaseService._cache_stats["hits"] += 1
        return entry.get_value()

    def _set_cached_value(
        self, cache_key: str, value: Any, ttl_seconds: int = 3600
    ) -> None:
        """Store value in cache with TTL.

        Args:
            cache_key: The cache key to store under.
            value: The value to cache.
            ttl_seconds: Time-to-live in seconds (default: 3600).
        """
        self._cache[cache_key] = CacheEntry(value, ttl_seconds)
        self.logger.debug(
            f"Cached value: {cache_key} (TTL: {ttl_seconds}s)"
        )

    def _invalidate_cache(self, pattern: Optional[str] = None) -> int:
        """Invalidate cache entries matching optional pattern.

        Args:
            pattern: Optional pattern to match cache keys. If None, clears
                all cache. Uses simple substring matching.

        Returns:
            Number of cache entries invalidated.
        """
        if pattern is None:
            # Clear all cache
            count = len(self._cache)
            self._cache.clear()
        else:
            # Clear matching keys
            keys_to_delete = [
                key for key in self._cache if pattern in key
            ]
            count = len(keys_to_delete)
            for key in keys_to_delete:
                del self._cache[key]

        BaseService._cache_stats["invalidations"] += count
        self.logger.info(f"Invalidated {count} cache entries (pattern: "
                        f"{pattern})")
        return count

    def _invalidate_cascade(
        self, entity_type: str, entity_id: int
    ) -> int:
        """Invalidate all cache entries dependent on an entity.

        When an entity is updated, all analyses that depend on that entity
        should be invalidated. This method clears the cascade.

        Args:
            entity_type: Type of entity (e.g., 'Place', 'Review').
            entity_id: ID of the entity being updated.

        Returns:
            Number of cache entries invalidated.
        """
        pattern = f"{entity_type}:{entity_id}"
        return self._invalidate_cache(pattern)

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache performance statistics.

        Returns:
            Dictionary with 'hits', 'misses', and 'invalidations' counts.
        """
        total = (
            BaseService._cache_stats["hits"] +
            BaseService._cache_stats["misses"]
        )
        stats = BaseService._cache_stats.copy()
        stats["total_requests"] = total
        if total > 0:
            stats["hit_ratio"] = (
                BaseService._cache_stats["hits"] / total
            )
        return stats

    def _transaction(self):
        """Context manager for atomic transaction handling.

        Automatically commits on success or rolls back on exception.
        Ensures ACID guarantees for service operations.

        Yields:
            The UnitOfWork instance for repository access.

        Raises:
            Re-raises any exception after rollback.
        """
        class TransactionContext:
            def __init__(self, service):
                self.service = service
                
            def __enter__(self):
                self.service.unit_of_work.begin()
                return self.service.unit_of_work
                
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    self.service.unit_of_work.commit()
                    self.service.logger.debug("Transaction committed")
                else:
                    self.service.unit_of_work.rollback()
                    self.service.logger.debug("Transaction rolled back")
                return False
        
        return TransactionContext(self)

    def _log_operation(
        self,
        operation: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log service operation with context.

        Args:
            operation: Type of operation (e.g., 'create', 'update', 'analyze').
            entity_type: Type of entity being operated on.
            entity_id: ID of the entity (optional).
            details: Additional operation details.
        """
        context = {
            "operation": operation,
            "entity_type": entity_type,
            "entity_id": entity_id,
            **(details or {}),
        }
        self.logger.info(
            f"Service operation: {operation} on {entity_type}"
            f"({entity_id})",
            extra=context,
        )

    def _log_error(
        self,
        message: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        exception: Optional[Exception] = None,
    ) -> None:
        """Log service error with context.

        Args:
            message: Error description.
            entity_type: Type of entity involved in error.
            entity_id: ID of the entity.
            exception: The exception that occurred.
        """
        context = {
            "entity_type": entity_type,
            "entity_id": entity_id,
        }
        self.logger.error(
            message,
            extra=context,
            exc_info=exception,
        )


__all__ = [
    "BaseService",
    "ServiceException",
    "ValidationException",
    "CacheEntry",
]
