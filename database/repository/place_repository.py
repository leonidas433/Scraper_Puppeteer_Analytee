"""
PlaceRepository - Place/business location data access.

Handles queries for place metadata, location searches, rating ranges,
and recent activity tracking.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database.models import Places, Reviews
from .base import BaseRepository


class PlaceRepository(BaseRepository[Places]):
    """Repository for Place entities.

    Specializes in location searches, rating queries, and activity tracking.
    """

    def __init__(self, session: Session):
        """Initialize PlaceRepository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, Places)

    # =====================================================================
    # Specialized Queries
    # =====================================================================

    def find_by_location(self, location: str, limit: int = 50) -> List[Places]:
        """Find places by location string.

        Args:
            location: Location name or substring
            limit: Maximum results

        Returns:
            List of matching places
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.location.ilike(f"%{location}%"))
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_name(self, name: str, limit: int = 50) -> List[Places]:
        """Find places by name substring.

        Args:
            name: Business name or substring
            limit: Maximum results

        Returns:
            List of matching places
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.name.ilike(f"%{name}%"))
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_rating_range(
        self, min_rating: float, max_rating: float = 5.0, limit: int = 100
    ) -> List[Places]:
        """Find places within rating range.

        Args:
            min_rating: Minimum rating (inclusive)
            max_rating: Maximum rating (inclusive, default 5.0)
            limit: Maximum results

        Returns:
            List of places within rating range
        """
        stmt = (
            select(self.entity_class)
            .where(
                (self.entity_class.rating >= min_rating)
                & (self.entity_class.rating <= max_rating)
            )
            .order_by(self.entity_class.rating.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_recent_activity(self, days: int = 7, limit: int = 50) -> List[Places]:
        """Find places with recent review activity.

        Args:
            days: Look back days (default 7)
            limit: Maximum results

        Returns:
            List of places with recent activity
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.last_scraped >= cutoff_date)
            .order_by(self.entity_class.last_scraped.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_top_rated(self, limit: int = 50) -> List[Places]:
        """Get highest rated places.

        Args:
            limit: Number of top places

        Returns:
            List of top rated places
        """
        stmt = (
            select(self.entity_class)
            .order_by(self.entity_class.rating.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_lowest_rated(self, limit: int = 50) -> List[Places]:
        """Get lowest rated places (for improvement focus).

        Args:
            limit: Number of lowest places

        Returns:
            List of lowest rated places
        """
        stmt = (
            select(self.entity_class)
            .order_by(self.entity_class.rating.asc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_stats(self) -> dict:
        """Get overall place statistics.

        Returns:
            Dict with avg_rating, total_places, total_reviews
        """
        avg_rating_stmt = select(func.avg(self.entity_class.rating)).scalar_subquery()
        total_places_stmt = select(func.count(self.entity_class.id)).scalar_subquery()

        avg_rating = self.session.execute(select(avg_rating_stmt)).scalar() or 0
        total_places = self.session.execute(select(total_places_stmt)).scalar() or 0

        return {
            "avg_rating": float(avg_rating),
            "total_places": total_places,
            "total_reviews": int(
                self.session.execute(select(func.sum(self.entity_class.total_reviews)))
                .scalar()
                or 0
            ),
        }

    def find_by_place_id(self, place_id: str) -> Optional[Places]:
        """Find place by external place_id.

        Args:
            place_id: External place identifier

        Returns:
            Place if found, None otherwise
        """
        stmt = select(self.entity_class).where(self.entity_class.place_id == place_id)
        return self.session.execute(stmt).scalars().first()

    def get_recent_places(self, days: int = 30, limit: int = 50) -> List[Places]:
        """Get recently scraped places.

        Args:
            days: Look back period
            limit: Maximum results

        Returns:
            Recently updated places
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.updated_at >= cutoff_date)
            .order_by(self.entity_class.updated_at.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()
