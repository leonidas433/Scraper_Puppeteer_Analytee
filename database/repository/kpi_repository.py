"""
KPIRepository - Key Performance Indicator (KPI) aggregation data access.

Handles temporal KPI aggregations, anomaly detection, and performance
metric queries.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from database.models import KPISummary, Places
from .base import BaseRepository


class KPIRepository(BaseRepository[KPISummary]):
    """Repository for KPI Summary entities.

    Specializes in temporal aggregations, anomaly detection, and metrics.
    """

    def __init__(self, session: Session):
        """Initialize KPIRepository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, KPISummary)

    # =====================================================================
    # Temporal KPI Queries
    # =====================================================================

    def find_by_place_and_period(
        self, place_id: str, period_start: datetime, period_end: datetime
    ) -> List[KPISummary]:
        """Get KPIs for place within period.

        Args:
            place_id: Place identifier
            period_start: Period start date
            period_end: Period end date

        Returns:
            KPI records for period
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.period_start >= period_start,
                    self.entity_class.period_end <= period_end,
                )
            )
            .order_by(self.entity_class.period_start.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_place_recent(self, place_id: str, periods: int = 12) -> List[KPISummary]:
        """Get recent KPI periods for place.

        Args:
            place_id: Place identifier
            periods: Number of periods to retrieve

        Returns:
            Recent KPI records
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.place_id == place_id)
            .order_by(self.entity_class.period_start.desc())
            .limit(periods)
        )
        results = self.session.execute(stmt).scalars().all()
        return list(reversed(results))  # Return in chronological order

    def find_by_time_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[KPISummary]:
        """Get all KPIs in date range.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            KPI records in range
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.period_start >= start_date,
                    self.entity_class.period_end <= end_date,
                )
            )
            .order_by(self.entity_class.period_start.asc())
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Aggregation Queries
    # =====================================================================

    def get_average_metrics(self, place_id: str) -> Dict[str, float]:
        """Get average metrics for place across all periods.

        Args:
            place_id: Place identifier

        Returns:
            Dict with avg_rating, avg_review_count, etc
        """
        stmt = (
            select(
                func.avg(self.entity_class.avg_rating),
                func.avg(self.entity_class.review_count),
                func.avg(self.entity_class.sentiment_score),
            )
            .where(self.entity_class.place_id == place_id)
        )
        result = self.session.execute(stmt).first()

        if result:
            return {
                "avg_rating": float(result[0] or 0),
                "avg_review_count": float(result[1] or 0),
                "avg_sentiment": float(result[2] or 0),
            }
        return {"avg_rating": 0, "avg_review_count": 0, "avg_sentiment": 0}

    def get_trending_places(
        self, metric: str = "avg_rating", limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get places sorted by metric.

        Args:
            metric: Metric to sort by (avg_rating, review_count, sentiment_score)
            limit: Number of results

        Returns:
            List of place metrics
        """
        if metric == "avg_rating":
            order_col = self.entity_class.avg_rating
        elif metric == "review_count":
            order_col = self.entity_class.review_count
        elif metric == "sentiment_score":
            order_col = self.entity_class.sentiment_score
        else:
            order_col = self.entity_class.avg_rating

        stmt = (
            select(self.entity_class)
            .order_by(order_col.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Anomaly Detection
    # =====================================================================

    def find_rating_drops(self, place_id: str, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Find periods where rating dropped significantly.

        Args:
            place_id: Place identifier
            threshold: Drop threshold

        Returns:
            Periods with drops
        """
        kpis = self.find_by_place_recent(place_id, periods=24)

        drops = []
        for i in range(1, len(kpis)):
            prev_rating = kpis[i - 1].avg_rating or 0
            curr_rating = kpis[i].avg_rating or 0
            drop = prev_rating - curr_rating

            if drop >= threshold:
                drops.append({
                    "period": kpis[i].period_start,
                    "previous_rating": prev_rating,
                    "current_rating": curr_rating,
                    "drop": drop,
                })

        return drops

    def find_rating_gains(self, place_id: str, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Find periods where rating improved significantly.

        Args:
            place_id: Place identifier
            threshold: Gain threshold

        Returns:
            Periods with gains
        """
        kpis = self.find_by_place_recent(place_id, periods=24)

        gains = []
        for i in range(1, len(kpis)):
            prev_rating = kpis[i - 1].avg_rating or 0
            curr_rating = kpis[i].avg_rating or 0
            gain = curr_rating - prev_rating

            if gain >= threshold:
                gains.append({
                    "period": kpis[i].period_start,
                    "previous_rating": prev_rating,
                    "current_rating": curr_rating,
                    "gain": gain,
                })

        return gains

    # =====================================================================
    # Comparison Queries
    # =====================================================================

    def compare_places_by_period(self, place_ids: List[str], period: datetime) -> Dict[str, Dict]:
        """Compare multiple places for a period.

        Args:
            place_ids: List of place identifiers
            period: Target period start date

        Returns:
            Dict mapping place_id to metrics
        """
        result = {}
        for place_id in place_ids:
            stmt = (
                select(self.entity_class)
                .where(
                    and_(
                        self.entity_class.place_id == place_id,
                        func.date(self.entity_class.period_start) == period.date(),
                    )
                )
                .limit(1)
            )
            kpi = self.session.execute(stmt).scalars().first()

            if kpi:
                result[place_id] = {
                    "avg_rating": kpi.avg_rating,
                    "review_count": kpi.review_count,
                    "sentiment_score": kpi.sentiment_score,
                }

        return result
