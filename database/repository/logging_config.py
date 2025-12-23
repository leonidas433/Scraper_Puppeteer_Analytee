"""
Audit logging configuration for repository operations.

Tracks all CRUD operations, query performance, transactions, and errors
for observability and debugging.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
import json


class AuditFormatter(logging.Formatter):
    """Custom formatter for audit trail logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with audit context."""
        log_dict = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add audit context if available
        if hasattr(record, "operation"):
            log_dict["operation"] = record.operation
        if hasattr(record, "entity_type"):
            log_dict["entity_type"] = record.entity_type
        if hasattr(record, "entity_id"):
            log_dict["entity_id"] = record.entity_id
        if hasattr(record, "duration_ms"):
            log_dict["duration_ms"] = record.duration_ms
        if hasattr(record, "row_count"):
            log_dict["row_count"] = record.row_count
        if hasattr(record, "context"):
            log_dict["context"] = record.context

        return json.dumps(log_dict)


def setup_audit_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """Setup audit logger for repository operations.

    Args:
        name: Logger name (typically __name__)
        level: Logging level

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Create console handler with audit formatter
    handler = logging.StreamHandler()
    handler.setFormatter(AuditFormatter())
    logger.addHandler(handler)

    return logger


class AuditLog:
    """Context manager for logging repository operations."""

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[Any] = None,
    ):
        """Initialize audit log context.

        Args:
            logger: Logger instance
            operation: Operation name (CREATE, READ, UPDATE, DELETE, QUERY)
            entity_type: Type of entity
            entity_id: ID of entity
        """
        self.logger = logger
        self.operation = operation
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.start_time = None
        self.row_count = None

    def __enter__(self):
        """Start operation timer."""
        self.start_time = datetime.utcnow()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log operation completion."""
        duration_ms = (datetime.utcnow() - self.start_time).total_seconds() * 1000

        extra = {
            "operation": self.operation,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "duration_ms": round(duration_ms, 2),
            "row_count": self.row_count,
        }

        if exc_type:
            self.logger.error(
                f"{self.operation} failed: {exc_val}",
                extra=extra,
            )
        else:
            self.logger.info(
                f"{self.operation} completed",
                extra=extra,
            )

    def set_row_count(self, count: int) -> None:
        """Set number of rows affected."""
        self.row_count = count


def log_crud_operation(
    operation: str,
    entity_type: str,
    entity_id: Optional[Any] = None,
    duration_ms: Optional[float] = None,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a CRUD operation.

    Args:
        operation: Operation type (CREATE, READ, UPDATE, DELETE)
        entity_type: Entity class name
        entity_id: Entity ID if applicable
        duration_ms: Operation duration in milliseconds
        context: Additional context information
    """
    logger = logging.getLogger("repository")

    extra = {
        "operation": operation,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "duration_ms": duration_ms,
        "context": context,
    }

    logger.info(f"{operation}: {entity_type}", extra=extra)


def log_query_execution(
    query_str: str,
    entity_type: str,
    duration_ms: float,
    row_count: int,
) -> None:
    """Log query execution.

    Args:
        query_str: Query description (not raw SQL)
        entity_type: Entity type being queried
        duration_ms: Execution time in milliseconds
        row_count: Rows returned
    """
    logger = logging.getLogger("repository.queries")

    extra = {
        "operation": "QUERY",
        "entity_type": entity_type,
        "duration_ms": duration_ms,
        "row_count": row_count,
    }

    if duration_ms > 100:
        logger.warning(
            f"Slow query ({duration_ms:.0f}ms): {query_str}",
            extra=extra,
        )
    else:
        logger.debug(f"Query: {query_str}", extra=extra)


def log_transaction(
    status: str,
    duration_ms: float,
    operations: int,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Log transaction lifecycle.

    Args:
        status: Transaction status (STARTED, COMMITTED, ROLLED_BACK)
        duration_ms: Transaction duration in milliseconds
        operations: Number of operations in transaction
        context: Transaction context
    """
    logger = logging.getLogger("repository.transactions")

    extra = {
        "operation": "TRANSACTION",
        "status": status,
        "duration_ms": duration_ms,
        "operations": operations,
        "context": context,
    }

    logger.info(f"Transaction {status}: {operations} ops in {duration_ms:.0f}ms", extra=extra)
