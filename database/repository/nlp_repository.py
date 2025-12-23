"""
NLPRepository - NLP analysis results data access.

Handles sentiment analysis trend queries, context filtering, language detection,
and latest analysis retrieval.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session

from database.models import NLPAnalysisResults, Reviews
from .base import BaseRepository


class NLPRepository(BaseRepository[NLPAnalysisResults]):
    """Repository for NLP Analysis Results.

    Specializes in sentiment analysis, language detection, and trend queries.
    """

    def __init__(self, session: Session):
        """Initialize NLPRepository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, NLPAnalysisResults)

    # =====================================================================
    # Sentiment Analysis
    # =====================================================================

    def find_by_review(self, review_id: str) -> Optional[NLPAnalysisResults]:
        """Get NLP analysis for review.

        Args:
            review_id: Review identifier

        Returns:
            NLP analysis if found
        """
        stmt = select(self.entity_class).where(self.entity_class.review_id == review_id)
        return self.session.execute(stmt).scalars().first()

    def find_by_sentiment(
        self, min_score: float, max_score: float = 1.0, limit: int = 100
    ) -> List[NLPAnalysisResults]:
        """Find analyses by sentiment score range.

        Args:
            min_score: Minimum sentiment score (-1 to 1)
            max_score: Maximum sentiment score
            limit: Maximum results

        Returns:
            Analyses within sentiment range
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.sentiment_score >= min_score,
                    self.entity_class.sentiment_score <= max_score,
                )
            )
            .order_by(self.entity_class.sentiment_score.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_negative_sentiment(self, threshold: float = -0.3, limit: int = 50) -> List[NLPAnalysisResults]:
        """Find negative sentiment analyses.

        Args:
            threshold: Sentiment threshold (default -0.3)
            limit: Maximum results

        Returns:
            Negative sentiment analyses
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.sentiment_score <= threshold)
            .order_by(self.entity_class.sentiment_score.asc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_positive_sentiment(self, threshold: float = 0.3, limit: int = 50) -> List[NLPAnalysisResults]:
        """Find positive sentiment analyses.

        Args:
            threshold: Sentiment threshold (default 0.3)
            limit: Maximum results

        Returns:
            Positive sentiment analyses
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.sentiment_score >= threshold)
            .order_by(self.entity_class.sentiment_score.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Context Filtering
    # =====================================================================

    def find_by_context(self, context_type: str, limit: int = 50) -> List[NLPAnalysisResults]:
        """Find analyses by context type.

        Args:
            context_type: Context classification
            limit: Maximum results

        Returns:
            Analyses with context
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.context.ilike(f"%{context_type}%"))
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_multiple_contexts(
        self, contexts: List[str], limit: int = 100
    ) -> List[NLPAnalysisResults]:
        """Find analyses matching any of multiple contexts.

        Args:
            contexts: List of context types
            limit: Maximum results

        Returns:
            Matching analyses
        """
        conditions = [self.entity_class.context.ilike(f"%{ctx}%") for ctx in contexts]
        stmt = (
            select(self.entity_class)
            .where(func.or_(*conditions))
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Language Detection
    # =====================================================================

    def find_by_language(self, language: str, limit: int = 100) -> List[NLPAnalysisResults]:
        """Find analyses by detected language.

        Args:
            language: Language code (e.g., 'en', 'es', 'fr')
            limit: Maximum results

        Returns:
            Analyses in language
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.language.ilike(language))
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_language_distribution(self) -> Dict[str, int]:
        """Get distribution of languages in analyses.

        Returns:
            Dict mapping language to count
        """
        stmt = select(
            self.entity_class.language,
            func.count(self.entity_class.id).label("count"),
        ).group_by(self.entity_class.language)

        results = self.session.execute(stmt).all()
        return {lang: count for lang, count in results}

    # =====================================================================
    # Trend Analysis
    # =====================================================================

    def get_latest_analyses(self, days: int = 7, limit: int = 50) -> List[NLPAnalysisResults]:
        """Get most recent NLP analyses.

        Args:
            days: Look back period
            limit: Maximum results

        Returns:
            Recent analyses
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.created_at >= cutoff)
            .order_by(self.entity_class.created_at.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_sentiment_trend(
        self, days: int = 30, intervals: int = 10
    ) -> List[Dict[str, Any]]:
        """Get sentiment trend over time.

        Args:
            days: Look back period
            intervals: Number of time intervals

        Returns:
            List of sentiment averages per interval
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.created_at >= cutoff)
            .order_by(self.entity_class.created_at.asc())
        )
        analyses = self.session.execute(stmt).scalars().all()

        if not analyses:
            return []

        # Divide into intervals
        interval_size = len(analyses) // max(intervals, 1)
        results = []

        for i in range(0, len(analyses), interval_size):
            batch = analyses[i : i + interval_size]
            avg_sentiment = sum(a.sentiment_score for a in batch) / len(batch) if batch else 0

            results.append({
                "period": batch[0].created_at if batch else None,
                "avg_sentiment": avg_sentiment,
                "count": len(batch),
            })

        return results

    # =====================================================================
    # Aggregation
    # =====================================================================

    def get_sentiment_statistics(self) -> Dict[str, float]:
        """Get overall sentiment statistics.

        Returns:
            Dict with avg, min, max, stdev sentiment
        """
        stmt = select(
            func.avg(self.entity_class.sentiment_score).label("avg"),
            func.min(self.entity_class.sentiment_score).label("min"),
            func.max(self.entity_class.sentiment_score).label("max"),
        )

        result = self.session.execute(stmt).first()

        return {
            "avg_sentiment": float(result.avg or 0),
            "min_sentiment": float(result.min or -1),
            "max_sentiment": float(result.max or 1),
        }

    def get_emotion_distribution(self) -> Dict[str, int]:
        """Get distribution of detected emotions.

        Returns:
            Dict mapping emotion to count
        """
        stmt = select(
            self.entity_class.emotions,
            func.count(self.entity_class.id).label("count"),
        ).group_by(self.entity_class.emotions)

        results = self.session.execute(stmt).all()
        distribution = {}

        for emotions_str, count in results:
            if emotions_str:
                for emotion in emotions_str.split(","):
                    emotion = emotion.strip()
                    distribution[emotion] = distribution.get(emotion, 0) + 1

        return distribution
