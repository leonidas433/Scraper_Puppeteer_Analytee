"""Pattern Detection Service - Identifies patterns in reviews and temporal data."""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from collections import Counter
import re

from database.service.base import BaseService
from database.service.validation.input_validator import InputValidator


logger = logging.getLogger(__name__)


class PatternDetectionService(BaseService):
    """Detects patterns in review text and temporal data."""

    def detect_text_patterns(
        self,
        place_id: int,
        min_frequency: int = 3,
    ) -> List[Dict]:
        """Detect keyword patterns in reviews."""
        InputValidator.validate_id(place_id, "place_id")

        cache_key = f"{self.__class__.__name__}.text.{place_id}.{min_frequency}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            with self._transaction():
                reviews = self._uow.reviews.filter(place_id=place_id)
                
                if not reviews:
                    return []

                keyword_freq = Counter()
                
                for review in reviews:
                    if hasattr(review, 'text') and review.text:
                        words = re.findall(r'\b[a-z]{4,}\b', review.text.lower())
                        stopwords = {'the', 'this', 'that', 'with', 'from', 'have', 'been', 'very', 'good', 'bad'}
                        words = [w for w in words if w not in stopwords]
                        keyword_freq.update(words)

                patterns = []
                for keyword, freq in keyword_freq.most_common():
                    if freq >= min_frequency:
                        patterns.append({
                            "type": "keyword",
                            "text": keyword,
                            "frequency": freq,
                            "confidence": min(freq / len(reviews), 1.0),
                        })

                self._cache.set(cache_key, patterns, ttl_seconds=3600)
                return patterns

        except Exception as e:
            logger.error(f"Pattern detection error: {str(e)}")
            return []

    def detect_temporal_patterns(
        self,
        place_id: int,
        window_days: int = 7,
    ) -> List[Dict]:
        """Detect temporal patterns in reviews."""
        InputValidator.validate_id(place_id, "place_id")

        cache_key = f"{self.__class__.__name__}.temporal.{place_id}.{window_days}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            with self._transaction():
                reviews = self._uow.reviews.filter(place_id=place_id)
                
                if not reviews:
                    return []

                day_counts = Counter()
                for review in reviews:
                    if hasattr(review, 'created_at') and review.created_at:
                        day_of_week = review.created_at.strftime("%A")
                        day_counts[day_of_week] += 1

                patterns = []
                if day_counts:
                    peak_day, peak_count = day_counts.most_common(1)[0]
                    patterns.append({
                        "type": "peak_day",
                        "text": peak_day,
                        "frequency": peak_count,
                        "confidence": peak_count / sum(day_counts.values()),
                    })

                self._cache.set(cache_key, patterns, ttl_seconds=3600)
                return patterns

        except Exception as e:
            logger.error(f"Temporal pattern error: {str(e)}")
            return []

    def detect_behavioral_anomalies(
        self,
        place_id: int,
        threshold: float = 0.8,
    ) -> List[Dict]:
        """Detect unusual behavioral patterns."""
        InputValidator.validate_id(place_id, "place_id")

        try:
            with self._transaction():
                reviews = self._uow.reviews.filter(place_id=place_id)
                
                if len(reviews) < 5:
                    return []

                recent_ratings = [r.rating for r in reviews[-20:] if hasattr(r, 'rating')]
                
                if not recent_ratings:
                    return []

                avg_rating = sum(recent_ratings) / len(recent_ratings)
                volatility = max(0, (max(recent_ratings) - min(recent_ratings)) / 5.0)

                patterns = []
                if volatility > threshold:
                    patterns.append({
                        "type": "rating_volatility",
                        "text": f"High volatility {volatility:.2f}",
                        "frequency": len(recent_ratings),
                        "confidence": volatility,
                    })

                return patterns

        except Exception as e:
            logger.error(f"Behavioral anomaly error: {str(e)}")
            return []

    def batch_pattern_detection(
        self,
        place_ids: List[int],
        pattern_types: Optional[List[str]] = None,
    ) -> Dict[int, List[Dict]]:
        """Batch pattern detection across multiple places."""
        if not place_ids:
            return {}

        if pattern_types is None:
            pattern_types = ["text", "temporal", "behavioral"]

        results = {}
        
        for place_id in place_ids:
            try:
                patterns = []
                if "text" in pattern_types:
                    patterns.extend(self.detect_text_patterns(place_id))
                if "temporal" in pattern_types:
                    patterns.extend(self.detect_temporal_patterns(place_id))
                if "behavioral" in pattern_types:
                    patterns.extend(self.detect_behavioral_anomalies(place_id))
                
                results[place_id] = patterns
            except Exception as e:
                logger.error(f"Batch detection failed for {place_id}: {str(e)}")
                results[place_id] = []
        
        return results
