"""
Unit of Work pattern for transaction management.

Provides atomic transaction context with automatic rollback on error
and lazy-loaded repository access.
"""

from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Generator
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .database_config import get_session
from .logging_config import log_transaction
from .error_handling import TransactionFailed


class UnitOfWork:
    """Unit of Work context manager for database transactions.

    Manages atomic operations across multiple repositories with
    automatic commit/rollback.

    Example:
        with UnitOfWork() as uow:
            place = uow.places.create(name="Coffee Shop")
            review = uow.reviews.create(place_id=place.id, rating=5)
            uow.commit()  # Atomic commit of both
    """

    def __init__(self, session: Optional[Session] = None):
        """Initialize Unit of Work.

        Args:
            session: Optional session (creates new if not provided)
        """
        self.session = session or get_session()
        self._repositories = {}
        self._start_time = None
        self._operation_count = 0

    # =====================================================================
    # Context Manager Protocol
    # =====================================================================

    def __enter__(self) -> "UnitOfWork":
        """Enter transaction context."""
        self._start_time = datetime.utcnow()
        log_transaction("STARTED", 0, 0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit transaction context with automatic cleanup.

        Args:
            exc_type: Exception type if occurred
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        try:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()

    # =====================================================================
    # Transaction Control
    # =====================================================================

    def commit(self) -> None:
        """Commit all changes in transaction.

        Raises:
            TransactionFailed: If commit fails
        """
        try:
            self.session.commit()
            duration_ms = (datetime.utcnow() - self._start_time).total_seconds() * 1000
            log_transaction("COMMITTED", duration_ms, self._operation_count)
        except SQLAlchemyError as e:
            self.session.rollback()
            raise TransactionFailed(f"Transaction commit failed: {str(e)}")

    def rollback(self) -> None:
        """Rollback all changes in transaction."""
        try:
            self.session.rollback()
            duration_ms = (datetime.utcnow() - self._start_time).total_seconds() * 1000
            log_transaction("ROLLED_BACK", duration_ms, self._operation_count)
        except SQLAlchemyError as e:
            raise TransactionFailed(f"Transaction rollback failed: {str(e)}")

    def close(self) -> None:
        """Close session."""
        self.session.close()

    def flush(self) -> None:
        """Flush pending changes to database without commit.

        Useful for getting generated IDs before commit.
        """
        try:
            self.session.flush()
            self._operation_count += 1
        except SQLAlchemyError as e:
            raise TransactionFailed(f"Session flush failed: {str(e)}")

    # =====================================================================
    # Repository Access (Lazy Loaded)
    # =====================================================================

    @property
    def places(self):
        """Get or create PlaceRepository."""
        if "places" not in self._repositories:
            from .place_repository import PlaceRepository
            self._repositories["places"] = PlaceRepository(self.session)
        return self._repositories["places"]

    @property
    def reviews(self):
        """Get or create ReviewRepository."""
        if "reviews" not in self._repositories:
            from .review_repository import ReviewRepository
            self._repositories["reviews"] = ReviewRepository(self.session)
        return self._repositories["reviews"]

    @property
    def kpis(self):
        """Get or create KPIRepository."""
        if "kpis" not in self._repositories:
            from .kpi_repository import KPIRepository
            self._repositories["kpis"] = KPIRepository(self.session)
        return self._repositories["kpis"]

    @property
    def cache(self):
        """Get or create CacheRepository."""
        if "cache" not in self._repositories:
            from .cache_repository import CacheRepository
            self._repositories["cache"] = CacheRepository(self.session)
        return self._repositories["cache"]

    @property
    def nlp_analyses(self):
        """Get or create NLPRepository."""
        if "nlp" not in self._repositories:
            from .nlp_repository import NLPRepository
            self._repositories["nlp"] = NLPRepository(self.session)
        return self._repositories["nlp"]

    @property
    def predictions(self):
        """Get or create PredictionRepository."""
        if "predictions" not in self._repositories:
            from .prediction_repository import PredictionRepository
            self._repositories["predictions"] = PredictionRepository(self.session)
        return self._repositories["predictions"]

    @property
    def correlations(self):
        """Get or create CorrelationRepository."""
        if "correlations" not in self._repositories:
            from .correlation_repository import CorrelationRepository
            self._repositories["correlations"] = CorrelationRepository(self.session)
        return self._repositories["correlations"]

    @property
    def clusters(self):
        """Get or create ClusterRepository."""
        if "clusters" not in self._repositories:
            from .cluster_repository import ClusterRepository
            self._repositories["clusters"] = ClusterRepository(self.session)
        return self._repositories["clusters"]

    @property
    def patterns(self):
        """Get or create PatternRepository."""
        if "patterns" not in self._repositories:
            from .pattern_repository import PatternRepository
            self._repositories["patterns"] = PatternRepository(self.session)
        return self._repositories["patterns"]

    @property
    def analytics_runs(self):
        """Get or create AnalyticsRunRepository."""
        if "runs" not in self._repositories:
            from .analytics_run_repository import AnalyticsRunRepository
            self._repositories["runs"] = AnalyticsRunRepository(self.session)
        return self._repositories["runs"]

    # =====================================================================
    # Context Factory
    # =====================================================================

    @staticmethod
    @contextmanager
    def transaction() -> Generator["UnitOfWork", None, None]:
        """Create transaction context.

        Recommended usage pattern:

            with UnitOfWork.transaction() as uow:
                entity = uow.entities.create(...)
                uow.commit()

        Yields:
            UnitOfWork instance
        """
        uow = UnitOfWork()
        try:
            yield uow
            uow.commit()
        except Exception:
            uow.rollback()
            raise
        finally:
            uow.close()
