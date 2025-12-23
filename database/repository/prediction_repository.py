"""
PredictionRepository - Predictive analytics data access.

Handles forecast range queries, confidence interval analysis, anomaly
detection, and prediction accuracy tracking.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from database.models import Predictions, Places
from .base import BaseRepository


class PredictionRepository(BaseRepository[Predictions]):
    """Repository for Prediction entities.

    Specializes in forecast queries, confidence analysis, and accuracy tracking.
    """

    def __init__(self, session: Session):
        """Initialize PredictionRepository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, Predictions)

    # =====================================================================
    # Forecast Queries
    # =====================================================================

    def find_by_place(self, place_id: str, limit: int = 50) -> List[Predictions]:
        """Get predictions for place.

        Args:
            place_id: Place identifier
            limit: Maximum results

        Returns:
            Place predictions
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.place_id == place_id)
            .order_by(self.entity_class.forecast_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_active_predictions(self, days: int = 90) -> List[Predictions]:
        """Get predictions that are still within forecast window.

        Args:
            days: Forecast window (default 90 days)

        Returns:
            Active predictions
        """
        cutoff = datetime.utcnow() + timedelta(days=days)
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.forecast_date <= cutoff)
            .order_by(self.entity_class.forecast_date.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_forecast_type(self, forecast_type: str, limit: int = 100) -> List[Predictions]:
        """Find predictions by type (rating, volume, etc).

        Args:
            forecast_type: Prediction type
            limit: Maximum results

        Returns:
            Matching predictions
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.forecast_type == forecast_type)
            .order_by(self.entity_class.forecast_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Confidence Interval Analysis
    # =====================================================================

    def find_high_confidence(
        self, min_confidence: float = 0.7, limit: int = 100
    ) -> List[Predictions]:
        """Find predictions with high confidence.

        Args:
            min_confidence: Minimum confidence threshold
            limit: Maximum results

        Returns:
            High confidence predictions
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.confidence_interval >= min_confidence)
            .order_by(self.entity_class.confidence_interval.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_low_confidence(
        self, max_confidence: float = 0.5, limit: int = 50
    ) -> List[Predictions]:
        """Find predictions with low confidence (uncertainty).

        Args:
            max_confidence: Maximum confidence threshold
            limit: Maximum results

        Returns:
            Low confidence predictions
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.confidence_interval <= max_confidence)
            .order_by(self.entity_class.confidence_interval.asc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_confidence_range(
        self, min_conf: float, max_conf: float, limit: int = 100
    ) -> List[Predictions]:
        """Find predictions within confidence range.

        Args:
            min_conf: Minimum confidence
            max_conf: Maximum confidence
            limit: Maximum results

        Returns:
            Matching predictions
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.confidence_interval >= min_conf,
                    self.entity_class.confidence_interval <= max_conf,
                )
            )
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Anomaly Detection
    # =====================================================================

    def find_anomalies(self, zscore_threshold: float = 2.0) -> List[Dict[str, Any]]:
        """Find anomalous predictions (outliers).

        Args:
            zscore_threshold: Z-score threshold for anomalies

        Returns:
            Anomalous predictions with details
        """
        all_preds = self.get_all()

        if not all_preds:
            return []

        # Calculate mean and stdev
        values = [p.predicted_value for p in all_preds if p.predicted_value]
        if not values:
            return []

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        stdev = variance ** 0.5

        anomalies = []
        for pred in all_preds:
            if pred.predicted_value and stdev > 0:
                zscore = abs((pred.predicted_value - mean) / stdev)
                if zscore >= zscore_threshold:
                    anomalies.append({
                        "prediction_id": pred.id,
                        "place_id": pred.place_id,
                        "value": pred.predicted_value,
                        "mean": mean,
                        "zscore": zscore,
                    })

        return anomalies

    # =====================================================================
    # Accuracy Tracking
    # =====================================================================

    def get_accuracy_stats(self) -> Dict[str, float]:
        """Get prediction accuracy statistics.

        Returns:
            Dict with accuracy metrics
        """
        stmt = select(
            func.avg(self.entity_class.prediction_error).label("avg_error"),
            func.min(self.entity_class.prediction_error).label("min_error"),
            func.max(self.entity_class.prediction_error).label("max_error"),
        ).where(self.entity_class.prediction_error.isnot(None))

        result = self.session.execute(stmt).first()

        if result.avg_error:
            accuracy = max(0, 100 - abs(float(result.avg_error) * 100))
        else:
            accuracy = 0

        return {
            "avg_error": float(result.avg_error or 0),
            "min_error": float(result.min_error or 0),
            "max_error": float(result.max_error or 0),
            "accuracy_percent": accuracy,
        }

    def get_accuracy_by_type(self) -> Dict[str, float]:
        """Get accuracy metrics per forecast type.

        Returns:
            Accuracy by forecast type
        """
        stmt = select(
            self.entity_class.forecast_type,
            func.avg(self.entity_class.prediction_error).label("avg_error"),
        ).group_by(self.entity_class.forecast_type)

        results = self.session.execute(stmt).all()

        return {
            forecast_type: max(0, 100 - abs(float(error) * 100))
            for forecast_type, error in results
            if error is not None
        }

    # =====================================================================
    # Trend & Comparison
    # =====================================================================

    def get_rating_predictions(self, place_id: str) -> List[Dict[str, Any]]:
        """Get rating forecast for place.

        Args:
            place_id: Place identifier

        Returns:
            Rating predictions
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.forecast_type == "rating",
                )
            )
            .order_by(self.entity_class.forecast_date.asc())
        )
        predictions = self.session.execute(stmt).scalars().all()

        return [
            {
                "date": p.forecast_date,
                "predicted_value": p.predicted_value,
                "confidence": p.confidence_interval,
                "lower_bound": getattr(p, "lower_bound", None),
                "upper_bound": getattr(p, "upper_bound", None),
            }
            for p in predictions
        ]

    def get_volume_predictions(self, place_id: str) -> List[Dict[str, Any]]:
        """Get review volume forecast for place.

        Args:
            place_id: Place identifier

        Returns:
            Volume predictions
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.forecast_type == "volume",
                )
            )
            .order_by(self.entity_class.forecast_date.asc())
        )
        predictions = self.session.execute(stmt).scalars().all()

        return [
            {
                "date": p.forecast_date,
                "predicted_value": p.predicted_value,
                "confidence": p.confidence_interval,
            }
            for p in predictions
        ]

    def compare_predictions(
        self, place_ids: List[str], forecast_date: datetime
    ) -> Dict[str, Dict[str, Any]]:
        """Compare predictions across places.

        Args:
            place_ids: Place identifiers
            forecast_date: Target forecast date

        Returns:
            Comparison dict
        """
        result = {}

        for place_id in place_ids:
            stmt = (
                select(self.entity_class)
                .where(
                    and_(
                        self.entity_class.place_id == place_id,
                        func.date(self.entity_class.forecast_date) == forecast_date.date(),
                    )
                )
                .limit(1)
            )
            pred = self.session.execute(stmt).scalars().first()

            if pred:
                result[place_id] = {
                    "value": pred.predicted_value,
                    "confidence": pred.confidence_interval,
                    "type": pred.forecast_type,
                }

        return result
