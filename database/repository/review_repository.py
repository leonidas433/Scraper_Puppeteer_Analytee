"""
ReviewRepository - Individual review data access.

Handles queries for place-based reviews, rating filters, owner response
tracking, and trend analysis.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from database.models import Reviews, Places
from .base import BaseRepository


class ReviewRepository(BaseRepository[Reviews]):
    """Repository for Review entities.

    Specializes in place-based queries, rating filtering, and trend analysis.
    """

    def __init__(self, session: Session):
        """Initialize ReviewRepository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, Reviews)

    # =====================================================================
    # Place-Based Queries
    # =====================================================================

    def find_by_place(self, place_id: str, limit: int = 100) -> List[Reviews]:
        """Get all reviews for a place.

        Args:
            place_id: Place identifier
            limit: Maximum results

        Returns:
            List of reviews for place
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.place_id == place_id)
            .order_by(self.entity_class.review_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_place_and_rating(
        self, place_id: str, min_rating: float, max_rating: float = 5.0, limit: int = 50
    ) -> List[Reviews]:
        """Get reviews for place within rating range.

        Args:
            place_id: Place identifier
            min_rating: Minimum rating
            max_rating: Maximum rating
            limit: Maximum results

        Returns:
            Filtered reviews
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.rating >= min_rating,
                    self.entity_class.rating <= max_rating,
                )
            )
            .order_by(self.entity_class.review_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_place_and_date_range(
        self, place_id: str, start_date: datetime, end_date: datetime, limit: int = 100
    ) -> List[Reviews]:
        """Get reviews for place within date range.

        Args:
            place_id: Place identifier
            start_date: Start date
            end_date: End date
            limit: Maximum results

        Returns:
            Reviews within date range
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.review_date >= start_date,
                    self.entity_class.review_date <= end_date,
                )
            )
            .order_by(self.entity_class.review_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Rating Queries
    # =====================================================================

    def find_low_ratings(self, place_id: str, threshold: float = 3.0) -> List[Reviews]:
        """Get low-rated reviews for a place.

        Args:
            place_id: Place identifier
            threshold: Rating threshold (default 3.0)

        Returns:
            Reviews below threshold
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.rating <= threshold,
                )
            )
            .order_by(self.entity_class.rating.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def find_high_ratings(self, place_id: str, threshold: float = 4.0) -> List[Reviews]:
        """Get high-rated reviews for a place.

        Args:
            place_id: Place identifier
            threshold: Rating threshold (default 4.0)

        Returns:
            Reviews above threshold
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.rating >= threshold,
                )
            )
            .order_by(self.entity_class.rating.desc())
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Owner Response Tracking
    # =====================================================================

    def find_with_owner_response(self, place_id: str) -> List[Reviews]:
        """Get reviews that have owner responses.

        Args:
            place_id: Place identifier

        Returns:
            Reviews with responses
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.has_owner_response == True,
                )
            )
            .order_by(self.entity_class.review_date.desc())
        )
        return self.session.execute(stmt).scalars().all()

    def find_without_owner_response(self, place_id: str) -> List[Reviews]:
        """Get reviews without owner responses.

        Args:
            place_id: Place identifier

        Returns:
            Reviews without responses
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.has_owner_response == False,
                )
            )
            .order_by(self.entity_class.review_date.desc())
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Trend Analysis
    # =====================================================================

    def get_average_rating(self, place_id: str) -> float:
        """Get average rating for place.

        Args:
            place_id: Place identifier

        Returns:
            Average rating
        """
        stmt = (
            select(func.avg(self.entity_class.rating))
            .where(self.entity_class.place_id == place_id)
        )
        result = self.session.execute(stmt).scalar()
        return float(result or 0)

    def get_rating_distribution(self, place_id: str) -> dict:
        """Get review rating distribution.

        Args:
            place_id: Place identifier

        Returns:
            Dict mapping rating to count
        """
        result = {}
        for rating in range(1, 6):
            count_stmt = (
                select(func.count(self.entity_class.id))
                .where(
                    and_(
                        self.entity_class.place_id == place_id,
                        self.entity_class.rating == float(rating),
                    )
                )
            )
            count = self.session.execute(count_stmt).scalar() or 0
            result[str(rating)] = int(count)
        return result

    def get_recent_reviews(self, place_id: str, days: int = 30, limit: int = 50) -> List[Reviews]:
        """Get recent reviews for place.

        Args:
            place_id: Place identifier
            days: Look back period
            limit: Maximum results

        Returns:
            Recent reviews
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.review_date >= cutoff,
                )
            )
            .order_by(self.entity_class.review_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()
