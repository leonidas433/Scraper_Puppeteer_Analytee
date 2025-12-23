"""
PatternRepository - Review pattern detection data access.

Handles active pattern detection, frequency-based filtering, trend analysis,
and pattern recommendations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session

from database.models import ReviewPatterns, Places
from .base import BaseRepository


class PatternRepository(BaseRepository[ReviewPatterns]):
    """Repository for Review Pattern entities.

    Specializes in behavioral pattern detection and trend analysis.
    """

    def __init__(self, session: Session):
        """Initialize PatternRepository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, ReviewPatterns)

    # =====================================================================
    # Pattern Detection
    # =====================================================================

    def find_by_place(self, place_id: str, limit: int = 50) -> List[ReviewPatterns]:
        """Get detected patterns for place.

        Args:
            place_id: Place identifier
            limit: Maximum results

        Returns:
            Patterns for place
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.place_id == place_id)
            .order_by(self.entity_class.frequency.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_active_patterns(self, place_id: Optional[str] = None) -> List[ReviewPatterns]:
        """Get currently active patterns.

        Args:
            place_id: Optional place filter

        Returns:
            Active patterns
        """
        stmt = select(self.entity_class).where(self.entity_class.is_active == True)

        if place_id:
            stmt = stmt.where(self.entity_class.place_id == place_id)

        return self.session.execute(stmt.order_by(self.entity_class.frequency.desc())).scalars().all()

    def find_inactive_patterns(self, place_id: Optional[str] = None) -> List[ReviewPatterns]:
        """Get inactive patterns.

        Args:
            place_id: Optional place filter

        Returns:
            Inactive patterns
        """
        stmt = select(self.entity_class).where(self.entity_class.is_active == False)

        if place_id:
            stmt = stmt.where(self.entity_class.place_id == place_id)

        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Frequency-Based Queries
    # =====================================================================

    def find_high_frequency_patterns(
        self, min_frequency: int = 10, limit: int = 50
    ) -> List[ReviewPatterns]:
        """Find frequently occurring patterns.

        Args:
            min_frequency: Minimum frequency threshold
            limit: Maximum results

        Returns:
            High frequency patterns
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.frequency >= min_frequency)
            .order_by(self.entity_class.frequency.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_rare_patterns(self, max_frequency: int = 3, limit: int = 50) -> List[ReviewPatterns]:
        """Find rarely occurring patterns.

        Args:
            max_frequency: Maximum frequency threshold
            limit: Maximum results

        Returns:
            Rare patterns
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.frequency <= max_frequency)
            .order_by(self.entity_class.frequency.asc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_frequency_range(
        self, min_freq: int, max_freq: int, limit: int = 100
    ) -> List[ReviewPatterns]:
        """Find patterns within frequency range.

        Args:
            min_freq: Minimum frequency
            max_freq: Maximum frequency
            limit: Maximum results

        Returns:
            Matching patterns
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.frequency >= min_freq,
                    self.entity_class.frequency <= max_freq,
                )
            )
            .order_by(self.entity_class.frequency.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Type & Category Queries
    # =====================================================================

    def find_by_pattern_type(self, pattern_type: str, limit: int = 100) -> List[ReviewPatterns]:
        """Find patterns by type.

        Args:
            pattern_type: Pattern type classification
            limit: Maximum results

        Returns:
            Patterns of type
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.pattern_type == pattern_type)
            .order_by(self.entity_class.frequency.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_pattern_types(self) -> Dict[str, int]:
        """Get distribution of pattern types.

        Returns:
            Count by pattern type
        """
        stmt = select(
            self.entity_class.pattern_type,
            func.count(self.entity_class.id).label("count"),
        ).group_by(self.entity_class.pattern_type)

        results = self.session.execute(stmt).all()
        return {ptype: count for ptype, count in results if ptype}

    # =====================================================================
    # Keyword & Content Analysis
    # =====================================================================

    def find_by_keyword(self, keyword: str, limit: int = 50) -> List[ReviewPatterns]:
        """Find patterns containing keyword.

        Args:
            keyword: Keyword to search
            limit: Maximum results

        Returns:
            Patterns with keyword
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.pattern_keywords.ilike(f"%{keyword}%"))
            .order_by(self.entity_class.frequency.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_multiple_keywords(
        self, keywords: List[str], limit: int = 100
    ) -> List[ReviewPatterns]:
        """Find patterns matching any keywords.

        Args:
            keywords: List of keywords
            limit: Maximum results

        Returns:
            Matching patterns
        """
        conditions = [self.entity_class.pattern_keywords.ilike(f"%{kw}%") for kw in keywords]
        stmt = (
            select(self.entity_class)
            .where(func.or_(*conditions))
            .order_by(self.entity_class.frequency.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Trend Analysis
    # =====================================================================

    def get_trending_patterns(self, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """Get trending patterns (emerging or growing).

        Args:
            days: Look back period
            limit: Maximum results

        Returns:
            Trending patterns
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.first_seen >= cutoff)
            .order_by(self.entity_class.frequency.desc())
            .limit(limit)
        )
        patterns = self.session.execute(stmt).scalars().all()

        return [
            {
                "pattern": p.pattern_keywords,
                "type": p.pattern_type,
                "frequency": p.frequency,
                "first_seen": p.first_seen,
                "last_seen": p.last_seen,
            }
            for p in patterns
        ]

    def get_recent_patterns(self, days: int = 7, limit: int = 50) -> List[ReviewPatterns]:
        """Get most recent patterns.

        Args:
            days: Look back period
            limit: Maximum results

        Returns:
            Recent patterns
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.last_seen >= cutoff)
            .order_by(self.entity_class.last_seen.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Recommendations
    # =====================================================================

    def find_pattern_recommendations(
        self, place_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get pattern-based recommendations for place.

        Args:
            place_id: Place identifier
            limit: Number of recommendations

        Returns:
            Recommended actions based on patterns
        """
        active_patterns = self.find_by_place(place_id)

        recommendations = []
        for pattern in active_patterns[:limit]:
            if pattern.frequency > 5:
                recommendations.append({
                    "pattern": pattern.pattern_keywords,
                    "type": pattern.pattern_type,
                    "frequency": pattern.frequency,
                    "recommendation": f"Address {pattern.pattern_type}: {pattern.pattern_keywords}",
                    "priority": "HIGH" if pattern.frequency > 20 else "MEDIUM",
                })

        return sorted(recommendations, key=lambda x: x["frequency"], reverse=True)

    # =====================================================================
    # Pattern Statistics
    # =====================================================================

    def get_pattern_statistics(self, place_id: Optional[str] = None) -> Dict[str, Any]:
        """Get pattern statistics.

        Args:
            place_id: Optional place filter

        Returns:
            Statistics dict
        """
        stmt = select(self.entity_class)

        if place_id:
            stmt = stmt.where(self.entity_class.place_id == place_id)

        patterns = self.session.execute(stmt).scalars().all()

        if not patterns:
            return {
                "total_patterns": 0,
                "active_patterns": 0,
                "avg_frequency": 0,
                "max_frequency": 0,
            }

        active_count = sum(1 for p in patterns if p.is_active)
        frequencies = [p.frequency for p in patterns]

        return {
            "total_patterns": len(patterns),
            "active_patterns": active_count,
            "avg_frequency": sum(frequencies) / len(frequencies) if frequencies else 0,
            "max_frequency": max(frequencies) if frequencies else 0,
        }

    def find_emerging_patterns(self, threshold_days: int = 7, limit: int = 20) -> List[ReviewPatterns]:
        """Find newly emerging patterns.

        Args:
            threshold_days: Pattern must be discovered within this many days
            limit: Maximum results

        Returns:
            Emerging patterns
        """
        cutoff = datetime.utcnow() - timedelta(days=threshold_days)
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.first_seen >= cutoff)
            .order_by(self.entity_class.frequency.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_declining_patterns(self) -> List[ReviewPatterns]:
        """Find patterns that are no longer active.

        Returns:
            Declining/inactive patterns
        """
        stmt = select(self.entity_class).where(
            and_(
                self.entity_class.is_active == False,
                self.entity_class.last_seen.isnot(None),
            )
        ).order_by(self.entity_class.last_seen.desc())

        return self.session.execute(stmt).scalars().all()
