"""
Abstract base repository for all domain repositories.

Provides generic CRUD operations, type-safe queries, and common
error handling patterns.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Any, Type
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, update
from sqlalchemy.exc import SQLAlchemyError

from .error_handling import handle_db_error, EntityNotFound, InvalidQuery
from .logging_config import log_crud_operation, log_query_execution, AuditLog

# Type variable for entity class
T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository for all domain entities.

    Provides type-safe CRUD operations, query building, and error handling.

    Type Parameters:
        T: The entity model class
    """

    def __init__(self, session: Session, entity_class: Type[T]):
        """Initialize repository.

        Args:
            session: SQLAlchemy session
            entity_class: Entity model class
        """
        self.session = session
        self.entity_class = entity_class

    # =====================================================================
    # CREATE Operations
    # =====================================================================

    def create(self, **kwargs) -> T:
        """Create and persist new entity.

        Args:
            **kwargs: Entity attributes

        Returns:
            Persisted entity

        Raises:
            DuplicateEntity: If unique constraint violated
            TransactionFailed: On database error
        """
        try:
            with AuditLog(
                self.session.get_bind().info.get("logger"),
                "CREATE",
                entity_type=self.entity_class.__name__,
            ) as log:
                entity = self.entity_class(**kwargs)
                self.session.add(entity)
                self.session.flush()
                log.set_row_count(1)
                return entity
        except SQLAlchemyError as e:
            raise handle_db_error(e, self.entity_class.__name__)

    def create_bulk(self, entities: List[T]) -> List[T]:
        """Create multiple entities in single transaction.

        Args:
            entities: List of entity instances

        Returns:
            List of persisted entities

        Raises:
            TransactionFailed: On database error
        """
        try:
            with AuditLog(
                self.session.get_bind().info.get("logger"),
                "CREATE_BULK",
                entity_type=self.entity_class.__name__,
            ) as log:
                self.session.add_all(entities)
                self.session.flush()
                log.set_row_count(len(entities))
                return entities
        except SQLAlchemyError as e:
            raise handle_db_error(e, self.entity_class.__name__)

    # =====================================================================
    # READ Operations
    # =====================================================================

    def get_by_id(self, entity_id: Any) -> T:
        """Get entity by primary key.

        Args:
            entity_id: Primary key value

        Returns:
            Entity instance

        Raises:
            EntityNotFound: If entity not found
            InvalidQuery: On query error
        """
        try:
            entity = self.session.get(self.entity_class, entity_id)
            if entity is None:
                raise EntityNotFound(
                    f"Entity not found by id",
                    entity_type=self.entity_class.__name__,
                    entity_id=entity_id,
                )
            return entity
        except SQLAlchemyError as e:
            raise handle_db_error(e, self.entity_class.__name__)

    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> List[T]:
        """Get all entities with optional pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of entities
        """
        try:
            stmt = select(self.entity_class).offset(offset)
            if limit:
                stmt = stmt.limit(limit)
            return self.session.execute(stmt).scalars().all()
        except SQLAlchemyError as e:
            raise handle_db_error(e, self.entity_class.__name__)

    def exists(self, **filters) -> bool:
        """Check if entity matching filters exists.

        Args:
            **filters: Filter conditions

        Returns:
            True if entity exists, False otherwise
        """
        try:
            stmt = select(self.entity_class).filter_by(**filters)
            return self.session.execute(stmt).scalars().first() is not None
        except SQLAlchemyError as e:
            raise handle_db_error(e, self.entity_class.__name__)

    # =====================================================================
    # UPDATE Operations
    # =====================================================================

    def update(self, entity_id: Any, **kwargs) -> T:
        """Update existing entity.

        Args:
            entity_id: Primary key
            **kwargs: Fields to update

        Returns:
            Updated entity

        Raises:
            EntityNotFound: If entity not found
        """
        try:
            entity = self.get_by_id(entity_id)
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            self.session.flush()
            return entity
        except SQLAlchemyError as e:
            raise handle_db_error(e, self.entity_class.__name__)

    def update_many(self, filter_dict: dict, update_dict: dict) -> int:
        """Update multiple entities matching filter.

        Args:
            filter_dict: Filters to match entities
            update_dict: Fields to update

        Returns:
            Number of entities updated
        """
        try:
            stmt = update(self.entity_class).filter_by(**filter_dict).values(**update_dict)
            result = self.session.execute(stmt)
            self.session.flush()
            return result.rowcount
        except SQLAlchemyError as e:
            raise handle_db_error(e, self.entity_class.__name__)

    # =====================================================================
    # DELETE Operations
    # =====================================================================

    def delete(self, entity_id: Any) -> bool:
        """Delete entity by primary key.

        Args:
            entity_id: Primary key

        Returns:
            True if deleted, False if not found

        Raises:
            TransactionFailed: On database error
        """
        try:
            entity = self.session.get(self.entity_class, entity_id)
            if entity is None:
                return False

            self.session.delete(entity)
            self.session.flush()
            return True
        except SQLAlchemyError as e:
            raise handle_db_error(e, self.entity_class.__name__)

    def delete_many(self, filter_dict: dict) -> int:
        """Delete multiple entities matching filter.

        Args:
            filter_dict: Filters to match entities

        Returns:
            Number of entities deleted
        """
        try:
            stmt = delete(self.entity_class).filter_by(**filter_dict)
            result = self.session.execute(stmt)
            self.session.flush()
            return result.rowcount
        except SQLAlchemyError as e:
            raise handle_db_error(e, self.entity_class.__name__)

    # =====================================================================
    # Helper Methods
    # =====================================================================

    def count(self, **filters) -> int:
        """Count entities matching filters.

        Args:
            **filters: Filter conditions

        Returns:
            Number of matching entities
        """
        try:
            from sqlalchemy import func
            stmt = select(func.count(self.entity_class.id)).filter_by(**filters)
            return self.session.execute(stmt).scalar() or 0
        except SQLAlchemyError as e:
            raise handle_db_error(e, self.entity_class.__name__)

    def clear_session(self) -> None:
        """Clear session cache."""
        self.session.expunge_all()
