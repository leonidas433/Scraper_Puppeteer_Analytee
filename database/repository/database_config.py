"""
Database configuration and session factory.

Supports SQLite (development) and PostgreSQL (production) with automatic
dialect detection and connection pooling.
"""

import os
from typing import Optional
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool, QueuePool


class DatabaseConfig:
    """Database configuration manager."""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize database config.

        Args:
            database_url: Database URL override (uses env var if not provided)
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "sqlite:///analytics.db"
        )
        self.is_sqlite = "sqlite" in self.database_url
        self.is_postgres = "postgresql" in self.database_url or "postgres" in self.database_url

    def create_engine(self) -> Engine:
        """Create SQLAlchemy engine with appropriate pooling.

        Returns:
            Configured SQLAlchemy engine
        """
        if self.is_sqlite:
            # SQLite: Use StaticPool for testing, NullPool for in-memory
            engine = create_engine(
                self.database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=os.getenv("SQL_ECHO", "false").lower() == "true",
            )
        elif self.is_postgres:
            # PostgreSQL: Use QueuePool with connection limits
            engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=20,
                max_overflow=40,
                pool_pre_ping=True,  # Verify connections before using
                echo=os.getenv("SQL_ECHO", "false").lower() == "true",
            )
        else:
            # Generic database
            engine = create_engine(
                self.database_url,
                echo=os.getenv("SQL_ECHO", "false").lower() == "true",
            )

        return engine

    def get_session_factory(self) -> sessionmaker:
        """Get configured session factory.

        Returns:
            sessionmaker instance
        """
        engine = self.create_engine()
        return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    def __str__(self) -> str:
        """String representation of config."""
        db_type = "SQLite" if self.is_sqlite else "PostgreSQL" if self.is_postgres else "Unknown"
        return f"DatabaseConfig({db_type})"


# Global session factory instance
_session_factory: Optional[sessionmaker] = None


def get_session_factory(database_url: Optional[str] = None) -> sessionmaker:
    """Get or create global session factory.

    Args:
        database_url: Database URL (only used for first call)

    Returns:
        Global sessionmaker instance
    """
    global _session_factory

    if _session_factory is None:
        config = DatabaseConfig(database_url)
        _session_factory = config.get_session_factory()

    return _session_factory


def reset_session_factory() -> None:
    """Reset global session factory (for testing)."""
    global _session_factory
    _session_factory = None


def get_session() -> Session:
    """Get new database session.

    Returns:
        New SQLAlchemy session
    """
    factory = get_session_factory()
    return factory()
