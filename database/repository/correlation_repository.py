"""
CorrelationRepository - Correlation analysis data access.

Handles factor driver ranking, response impact analysis, type-based queries,
and relationship strength queries.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session

from database.models import CorrelationAnalysis, Places
from .base import BaseRepository


class CorrelationRepository(BaseRepository[CorrelationAnalysis]):
    """Repository for Correlation Analysis entities.

    Specializes in factor analysis, impact assessment, and relationship queries.
    """

    def __init__(self, session: Session):
        """Initialize CorrelationRepository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, CorrelationAnalysis)

    # =====================================================================
    # Factor Analysis
    # =====================================================================

    def find_by_place(self, place_id: str, limit: int = 50) -> List[CorrelationAnalysis]:
        """Get correlation analysis for place.

        Args:
            place_id: Place identifier
            limit: Maximum results

        Returns:
            Correlations for place
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.place_id == place_id)
            .order_by(self.entity_class.correlation_coefficient.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_top_factors(self, place_id: str, limit: int = 20) -> List[CorrelationAnalysis]:
        """Get strongest correlation factors for place.

        Args:
            place_id: Place identifier
            limit: Number of top factors

        Returns:
            Top correlated factors
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.place_id == place_id)
            .order_by(desc(func.abs(self.entity_class.correlation_coefficient)))
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_factor_type(self, factor_type: str, limit: int = 100) -> List[CorrelationAnalysis]:
        """Find correlations by factor type.

        Args:
            factor_type: Type of factor (e.g., 'cleanliness', 'service')
            limit: Maximum results

        Returns:
            Correlations for factor type
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.factor_name == factor_type)
            .order_by(self.entity_class.correlation_coefficient.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Strength & Direction Analysis
    # =====================================================================

    def find_strong_positive_correlations(
        self, threshold: float = 0.5, limit: int = 100
    ) -> List[CorrelationAnalysis]:
        """Find strong positive correlations.

        Args:
            threshold: Correlation coefficient threshold
            limit: Maximum results

        Returns:
            Strong positive correlations
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.correlation_coefficient >= threshold)
            .order_by(self.entity_class.correlation_coefficient.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_strong_negative_correlations(
        self, threshold: float = -0.5, limit: int = 100
    ) -> List[CorrelationAnalysis]:
        """Find strong negative correlations.

        Args:
            threshold: Correlation coefficient threshold
            limit: Maximum results

        Returns:
            Strong negative correlations
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.correlation_coefficient <= threshold)
            .order_by(self.entity_class.correlation_coefficient.asc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_weak_correlations(
        self, max_strength: float = 0.3, limit: int = 100
    ) -> List[CorrelationAnalysis]:
        """Find weak correlations (close to 0).

        Args:
            max_strength: Maximum absolute correlation
            limit: Maximum results

        Returns:
            Weak correlations
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    func.abs(self.entity_class.correlation_coefficient) <= max_strength,
                )
            )
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Impact Analysis
    # =====================================================================

    def find_by_impact_level(self, impact_level: str) -> List[CorrelationAnalysis]:
        """Find correlations by impact level.

        Args:
            impact_level: Impact classification (HIGH, MEDIUM, LOW)

        Returns:
            Correlations with level
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.impact_level == impact_level)
            .order_by(self.entity_class.correlation_coefficient.desc())
        )
        return self.session.execute(stmt).scalars().all()

    def get_impact_distribution(self) -> Dict[str, int]:
        """Get distribution of impact levels.

        Returns:
            Count by impact level
        """
        stmt = select(
            self.entity_class.impact_level,
            func.count(self.entity_class.id).label("count"),
        ).group_by(self.entity_class.impact_level)

        results = self.session.execute(stmt).all()
        return {level: count for level, count in results if level}

    # =====================================================================
    # Response Impact
    # =====================================================================

    def find_response_impact(self, place_id: str) -> List[CorrelationAnalysis]:
        """Find factors correlated with owner response.

        Args:
            place_id: Place identifier

        Returns:
            Response-related correlations
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.factor_name.ilike("%response%"),
                )
            )
            .order_by(self.entity_class.correlation_coefficient.desc())
        )
        return self.session.execute(stmt).scalars().all()

    def find_rating_drivers(self, place_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get factors most correlated with ratings.

        Args:
            place_id: Place identifier
            limit: Maximum factors

        Returns:
            Rating driver factors
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.variable_name.ilike("%rating%"),
                )
            )
            .order_by(desc(func.abs(self.entity_class.correlation_coefficient)))
            .limit(limit)
        )
        correlations = self.session.execute(stmt).scalars().all()

        return [
            {
                "factor": c.factor_name,
                "correlation": c.correlation_coefficient,
                "impact": c.impact_level,
                "p_value": getattr(c, "p_value", None),
            }
            for c in correlations
        ]

    # =====================================================================
    # Type Analysis
    # =====================================================================

    def find_by_variable(self, variable_name: str, limit: int = 100) -> List[CorrelationAnalysis]:
        """Find correlations for specific variable.

        Args:
            variable_name: Variable being analyzed
            limit: Maximum results

        Returns:
            Correlations with variable
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.variable_name == variable_name)
            .order_by(self.entity_class.correlation_coefficient.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_factor_importance(self) -> Dict[str, float]:
        """Get ranking of factor importance across all analyses.

        Returns:
            Factor names ranked by importance
        """
        stmt = select(
            self.entity_class.factor_name,
            func.avg(func.abs(self.entity_class.correlation_coefficient)).label("avg_strength"),
        ).group_by(self.entity_class.factor_name).order_by(desc("avg_strength"))

        results = self.session.execute(stmt).all()
        return {factor: float(strength) for factor, strength in results}

    # =====================================================================
    # Time Series Analysis
    # =====================================================================

    def get_recent_correlations(self, days: int = 30, limit: int = 50) -> List[CorrelationAnalysis]:
        """Get most recent correlation analyses.

        Args:
            days: Look back period
            limit: Maximum results

        Returns:
            Recent correlations
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.analysis_date >= cutoff)
            .order_by(self.entity_class.analysis_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def track_factor_evolution(self, place_id: str, factor_name: str) -> List[Dict[str, Any]]:
        """Track how factor correlation changes over time.

        Args:
            place_id: Place identifier
            factor_name: Factor to track

        Returns:
            Time series of correlation values
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.factor_name == factor_name,
                )
            )
            .order_by(self.entity_class.analysis_date.asc())
        )
        correlations = self.session.execute(stmt).scalars().all()

        return [
            {
                "date": c.analysis_date,
                "correlation": c.correlation_coefficient,
                "impact": c.impact_level,
            }
            for c in correlations
        ]
