"""
CacheRepository - Performance caching layer data access.

Handles TTL-based caching with expiration management for frequently
accessed query results.
"""

from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from database.models import AnalysisCacheEntry
from .base import BaseRepository


class CacheRepository(BaseRepository[AnalysisCacheEntry]):
    """Repository for AnalysisCacheEntry entities.

    Specializes in TTL-based caching with automatic expiration management.
    """

    def __init__(self, session: Session):
        """Initialize CacheRepository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, AnalysisCacheEntry)

    # =====================================================================
    # Cache Access
    # =====================================================================

    def get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached data dict if found and valid, None otherwise
        """
        stmt = select(self.entity_class).where(self.entity_class.cache_key == key)
        cache_entry = self.session.execute(stmt).scalars().first()

        if not cache_entry:
            return None

        # Check expiration
        if cache_entry.expires_at and cache_entry.expires_at < datetime.utcnow():
            self.delete(cache_entry.id)
            return None

        return cache_entry.cached_data

    def set_cached(
        self, key: str, data: Dict[str, Any], ttl_minutes: int = 60
    ) -> AnalysisCacheEntry:
        """Set cache value with TTL.

        Args:
            key: Cache key
            data: Data to cache
            ttl_minutes: Time-to-live in minutes

        Returns:
            Cache entry
        """
        # Check if key exists
        stmt = select(self.entity_class).where(self.entity_class.cache_key == key)
        existing = self.session.execute(stmt).scalars().first()

        expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)

        if existing:
            existing.cached_data = data
            existing.expires_at = expires_at
            existing.updated_at = datetime.utcnow()
            self.session.flush()
            return existing
        else:
            return self.create(
                cache_key=key,
                cached_data=data,
                expires_at=expires_at,
            )

    # =====================================================================
    # Expiration Management
    # =====================================================================

    def cleanup_expired(self) -> int:
        """Remove all expired cache entries.

        Returns:
            Number of entries deleted
        """
        stmt = select(self.entity_class).where(
            self.entity_class.expires_at < datetime.utcnow()
        )
        expired = self.session.execute(stmt).scalars().all()

        count = 0
        for entry in expired:
            self.session.delete(entry)
            count += 1

        self.session.flush()
        return count

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache_size, expired_count, avg_ttl_minutes
        """
        total_stmt = select(func.count(self.entity_class.id))
        total = self.session.execute(total_stmt).scalar() or 0

        expired_stmt = select(func.count(self.entity_class.id)).where(
            self.entity_class.expires_at < datetime.utcnow()
        )
        expired = self.session.execute(expired_stmt).scalar() or 0

        # Calculate average remaining TTL
        now = datetime.utcnow()
        avg_ttl_stmt = select(
            func.avg(
                func.extract(
                    "epoch",
                    self.entity_class.expires_at - now,
                )
            )
        ).where(self.entity_class.expires_at >= now)

        avg_ttl_seconds = self.session.execute(avg_ttl_stmt).scalar() or 0
        avg_ttl_minutes = avg_ttl_seconds / 60

        return {
            "total_entries": int(total),
            "expired_entries": int(expired),
            "valid_entries": int(total - expired),
            "avg_ttl_minutes": round(avg_ttl_minutes, 1),
        }

    # =====================================================================
    # Pattern-Based Access
    # =====================================================================

    def find_by_key_pattern(self, pattern: str) -> List[AnalysisCacheEntry]:
        """Find cache entries by key pattern.

        Args:
            pattern: Key pattern (supports wildcards)

        Returns:
            Matching cache entries
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.cache_key.ilike(pattern))
            .where(self.entity_class.expires_at >= datetime.utcnow())
        )
        return self.session.execute(stmt).scalars().all()

    def clear_by_pattern(self, pattern: str) -> int:
        """Delete cache entries matching pattern.

        Args:
            pattern: Key pattern

        Returns:
            Number of entries deleted
        """
        stmt = select(self.entity_class).where(
            self.entity_class.cache_key.ilike(pattern)
        )
        entries = self.session.execute(stmt).scalars().all()

        count = 0
        for entry in entries:
            self.session.delete(entry)
            count += 1

        self.session.flush()
        return count

    # =====================================================================
    # Optimization
    # =====================================================================

    def get_most_accessed(self, limit: int = 20) -> List[AnalysisCacheEntry]:
        """Get most frequently accessed cache entries.

        Args:
            limit: Number of entries

        Returns:
            Most accessed entries
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.expires_at >= datetime.utcnow())
            .order_by(self.entity_class.access_count.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def increment_access_count(self, key: str) -> Optional[AnalysisCacheEntry]:
        """Increment access count for cache key.

        Args:
            key: Cache key

        Returns:
            Updated cache entry if found
        """
        stmt = select(self.entity_class).where(self.entity_class.cache_key == key)
        entry = self.session.execute(stmt).scalars().first()

        if entry:
            entry.access_count = (entry.access_count or 0) + 1
            entry.last_accessed = datetime.utcnow()
            self.session.flush()
            return entry

        return None

    def clear_all_cache(self) -> int:
        """Clear entire cache (use with caution).

        Returns:
            Number of entries deleted
        """
        return self.delete_many({})


