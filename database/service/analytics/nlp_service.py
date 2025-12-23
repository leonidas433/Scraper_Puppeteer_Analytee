"""NLP Service for sentiment analysis, emotions, and language insights.

This service extracts sentiment scores, emotional trajectories, and key
phrases from reviews. It provides both individual place analysis and
batch processing capabilities.

Key Features:
    - Sentiment analysis using weighted TextBlob + custom lexicon
    - Emotion detection with intensity scoring
    - Trend calculation using linear regression
    - TTL-based caching (1 hour)
    - Transaction-safe operations
    - Comprehensive error context

Example:
    >>> from database.service.analytics import NLPService
    >>> from database.repository.unit_of_work import UnitOfWork
    >>> uow = UnitOfWork(...)
    >>> nlp_service = NLPService(uow)
    >>> result = nlp_service.analyze_sentiment(
    ...     place_id="place_123",
    ...     date_range=DateRangeDTO(start=date(2024, 1, 1), end=date(2024, 1, 31))
    ... )
    >>> print(f"Sentiment: {result.sentiment_score}")
    Sentiment: 0.75
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import logging

from database.service.base import BaseService, ServiceException, ValidationException
from database.service.validation import (
    InputValidator,
    DomainValidator,
    CrossEntityValidator,
    BusinessRuleValidator,
)
from database.service.dto import (
    DateRangeDTO,
    NLPResultDTO,
    TrendDTO,
    DTOTransformer,
)
from database.repository.unit_of_work import UnitOfWork


logger = logging.getLogger(__name__)


class NLPService(BaseService):
    """Service for Natural Language Processing analytics on reviews.
    
    Performs sentiment analysis, emotion detection, and language analysis
    on review text. Supports both single-place and batch analysis with
    caching and transaction safety.
    """

    def __init__(self, unit_of_work: UnitOfWork) -> None:
        """Initialize NLPService.
        
        Args:
            unit_of_work: UnitOfWork instance for repository access and
                transaction management.
        """
        super().__init__(unit_of_work)
        logger.info("NLPService initialized")

    def analyze_sentiment(
        self,
        place_id: str,
        date_range: Optional[DateRangeDTO] = None,
    ) -> NLPResultDTO:
        """Analyze sentiment and emotions for a place over date range.
        
        Performs comprehensive sentiment analysis including sentiment score,
        emotional trajectory, key phrases, and language insights. Results
        are cached for 1 hour to improve performance.
        
        Args:
            place_id: Unique identifier for the place to analyze.
            date_range: Optional date range (default: last 90 days).
                If None, analyzes last 90 days of reviews.
        
        Returns:
            NLPResultDTO containing sentiment_score, confidence, emotions,
            key_phrases, emotional_trajectory, and language_insights.
        
        Raises:
            ValidationException: If place_id format invalid or date_range
                parameters are invalid.
            ServiceException: If place doesn't exist, insufficient historical
                data, or NLP processing fails.
        
        Example:
            >>> result = nlp_service.analyze_sentiment(
            ...     place_id="place_123",
            ...     date_range=DateRangeDTO(
            ...         start=date(2024, 1, 1),
            ...         end=date(2024, 1, 31)
            ...     )
            ... )
            >>> print(f"Sentiment: {result.sentiment_score}")
            >>> print(f"Emotions: {result.emotions}")
        """
        # Layer 1: Input Validation (before transaction)
        logger.info(f"Starting sentiment analysis for place: {place_id}")
        InputValidator.validate_place_id(place_id)
        
        # Default to last 90 days if not provided
        if date_range is None:
            end_date = date.today()
            start_date = end_date - timedelta(days=90)
            date_range = DateRangeDTO(start=start_date, end=end_date)
        else:
            InputValidator.validate_date_range(
                date_range.start, date_range.end
            )
        
        # Check cache before transaction
        cache_key = self._generate_cache_key(
            "sentiment", place_id, date_range.start, date_range.end
        )
        cached_result = self.get_cached(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for {cache_key}")
            return cached_result
        
        # Execute analysis within transaction
        with self._transaction():
            # Layer 2: Domain Validation (inside transaction)
            DomainValidator.validate_place_exists(
                place_id, self.unit_of_work
            )
            DomainValidator.validate_sufficient_historical_data(
                place_id,
                min_reviews=5,
                min_days=30,
                unit_of_work=self.unit_of_work,
            )
            
            logger.debug(f"Domain validation passed for {place_id}")
            
            # Layer 3: Cross-Entity Validation (inside transaction)
            # All reviews must belong to the place (validated in repo fetch)
            
            # Fetch reviews for analysis
            try:
                reviews = self.unit_of_work.reviews.get_reviews_for_place(
                    place_id, date_range.start, date_range.end
                )
            except Exception as e:
                raise ServiceException(
                    error_code="REVIEW_FETCH_FAILED",
                    message=f"Failed to fetch reviews for {place_id}",
                    context={
                        "place_id": place_id,
                        "start_date": str(date_range.start),
                        "end_date": str(date_range.end),
                        "error": str(e),
                    },
                )
            
            if not reviews:
                raise ServiceException(
                    error_code="NO_REVIEWS_FOUND",
                    message=f"No reviews found for {place_id} in date range",
                    context={
                        "place_id": place_id,
                        "start_date": str(date_range.start),
                        "end_date": str(date_range.end),
                        "review_count": 0,
                    },
                )
            
            # Perform sentiment analysis on reviews
            result_dto = self._perform_sentiment_analysis(
                place_id, reviews, date_range
            )
            
            logger.info(
                f"Sentiment analysis complete for {place_id}: "
                f"score={result_dto.sentiment_score}"
            )
        
        # Cache result for 1 hour (3600 seconds)
        self.set_cached(cache_key, result_dto, ttl=3600)
        
        # Cascade invalidation key: sentiment analyses invalidate on new review
        self._register_invalidation_pattern("sentiment_*")
        
        return result_dto

    def get_sentiment_trend(
        self,
        place_id: str,
        period: int = 30,
    ) -> TrendDTO:
        """Calculate sentiment trend over specified period.
        
        Analyzes how sentiment has been changing over the specified number
        of days. Returns trend direction, strength, and percentage change.
        
        Args:
            place_id: Unique identifier for the place.
            period: Number of days to analyze (default: 30).
        
        Returns:
            TrendDTO with direction, strength, and change percentage.
        
        Raises:
            ValidationException: If place_id invalid or period out of range.
            ServiceException: If insufficient historical data.
        
        Example:
            >>> trend = nlp_service.get_sentiment_trend(
            ...     place_id="place_123",
            ...     period=30
            ... )
            >>> print(f"Trend: {trend.direction}, Change: {trend.change_percent}%")
        """
        logger.info(f"Calculating sentiment trend for {place_id} ({period}d)")
        
        # Layer 1: Input Validation
        InputValidator.validate_place_id(place_id)
        InputValidator.validate_numeric_range(period, 1, 365)
        
        # Check cache
        cache_key = self._generate_cache_key(
            "sentiment_trend", place_id, period
        )
        cached_result = self.get_cached(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit for {cache_key}")
            return cached_result
        
        with self._transaction():
            # Layer 2: Domain Validation
            DomainValidator.validate_place_exists(
                place_id, self.unit_of_work
            )
            
            # Fetch sentiment scores over time
            end_date = date.today()
            start_date = end_date - timedelta(days=period)
            
            try:
                reviews = self.unit_of_work.reviews.get_reviews_for_place(
                    place_id, start_date, end_date
                )
            except Exception as e:
                raise ServiceException(
                    error_code="TREND_CALC_FAILED",
                    message=f"Failed to calculate trend for {place_id}",
                    context={"place_id": place_id, "period": period, "error": str(e)},
                )
            
            if len(reviews) < 3:
                raise ServiceException(
                    error_code="INSUFFICIENT_DATA",
                    message=f"Insufficient data for trend analysis ({len(reviews)} reviews)",
                    context={"place_id": place_id, "review_count": len(reviews)},
                )
            
            # Calculate trend using linear regression
            trend_dto = self._calculate_trend_linear_regression(
                place_id, reviews
            )
        
        # Cache for 1 hour
        self.set_cached(cache_key, trend_dto, ttl=3600)
        return trend_dto

    def batch_analyze_places(
        self,
        place_ids: List[str],
        max_workers: int = 5,
    ) -> Dict[str, NLPResultDTO]:
        """Perform sentiment analysis for multiple places in parallel.
        
        Analyzes sentiment for a batch of places using parallel execution.
        Handles partial failures gracefully - returns successful results
        and error information for failed places.
        
        Args:
            place_ids: List of place identifiers to analyze.
            max_workers: Maximum parallel workers (default: 5).
        
        Returns:
            Dictionary mapping place_id to NLPResultDTO for successful
            analyses. Failed places are logged but not included.
        
        Raises:
            ValidationException: If place_ids list is empty or invalid.
            ServiceException: If batch processing fails catastrophically.
        
        Example:
            >>> results = nlp_service.batch_analyze_places(
            ...     place_ids=["place_1", "place_2", "place_3"]
            ... )
            >>> for place_id, result in results.items():
            ...     print(f"{place_id}: {result.sentiment_score}")
        """
        logger.info(f"Starting batch analysis for {len(place_ids)} places")
        
        # Layer 1: Input Validation
        InputValidator.validate_list_not_empty(place_ids, item_type=str)
        
        results: Dict[str, NLPResultDTO] = {}
        errors: Dict[str, str] = {}
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                futures = {
                    executor.submit(
                        self.analyze_sentiment, place_id
                    ): place_id
                    for place_id in place_ids
                }
                
                # Collect results as they complete
                for future in as_completed(futures):
                    place_id = futures[future]
                    try:
                        result = future.result(timeout=300)  # 5 min timeout
                        results[place_id] = result
                        logger.debug(f"✓ Analyzed {place_id}")
                    except ValidationException as e:
                        errors[place_id] = f"Validation failed: {e.message}"
                        logger.warning(f"✗ {place_id}: {e.message}")
                    except ServiceException as e:
                        errors[place_id] = f"Service error: {e.message}"
                        logger.warning(f"✗ {place_id}: {e.message}")
                    except Exception as e:
                        errors[place_id] = f"Unexpected error: {str(e)}"
                        logger.error(f"✗ {place_id}: {str(e)}")
        
        except Exception as e:
            raise ServiceException(
                error_code="BATCH_ANALYSIS_FAILED",
                message=f"Batch analysis failed: {str(e)}",
                context={"place_count": len(place_ids), "error": str(e)},
            )
        
        logger.info(
            f"Batch analysis complete: {len(results)} succeeded, "
            f"{len(errors)} failed"
        )
        
        if errors:
            logger.warning(f"Errors in batch analysis: {errors}")
        
        return results

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _perform_sentiment_analysis(
        self,
        place_id: str,
        reviews: List[Any],
        date_range: DateRangeDTO,
    ) -> NLPResultDTO:
        """Perform actual sentiment analysis on review collection.
        
        Args:
            place_id: Place identifier.
            reviews: List of review objects.
            date_range: Analysis date range.
        
        Returns:
            NLPResultDTO with complete analysis results.
        """
        # Extract sentiment scores from review texts
        sentiment_scores = []
        emotions_aggregate: Dict[str, float] = {}
        key_phrases: List[str] = []
        
        for review in reviews:
            # Calculate individual sentiment (0-1 scale, 0.5 = neutral)
            text = getattr(review, "text", "")
            rating = getattr(review, "rating", 3.0)
            
            # Combine TextBlob polarity with rating for better accuracy
            # TextBlob polarity: -1 to 1, normalize to 0-1
            polarity_normalized = (self._calculate_polarity(text) + 1) / 2
            rating_normalized = min(rating / 5.0, 1.0)
            
            # Weighted combination (60% text, 40% rating)
            sentiment_score = (polarity_normalized * 0.6) + (rating_normalized * 0.4)
            sentiment_scores.append(sentiment_score)
            
            # Extract emotions
            emotions = self._extract_emotions(text)
            for emotion, intensity in emotions.items():
                emotions_aggregate[emotion] = emotions_aggregate.get(emotion, 0.0) + intensity
            
            # Extract key phrases
            phrases = self._extract_key_phrases(text)
            key_phrases.extend(phrases)
        
        # Aggregate metrics
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.5
        # Convert from 0-1 to -1 to 1 range for API output
        sentiment_score = (avg_sentiment * 2) - 1
        
        # Normalize emotions
        if emotions_aggregate and sentiment_scores:
            for emotion in emotions_aggregate:
                emotions_aggregate[emotion] /= len(sentiment_scores)
        
        # Get unique key phrases and limit to top 10
        unique_phrases = list(set(key_phrases))[:10]
        
        # Calculate confidence based on number and consistency of reviews
        confidence = min(len(sentiment_scores) / 10.0, 1.0)  # Max at 10 reviews
        confidence *= (1.0 - (sum(abs(s - avg_sentiment) for s in sentiment_scores) / len(sentiment_scores)))
        confidence = max(0.0, min(confidence, 1.0))
        
        # Calculate emotional trajectory (trend)
        emotional_trajectory = self._calculate_trend_linear_regression(
            place_id, reviews
        )
        
        # Language insights
        language_insights = self._extract_language_insights(reviews)
        
        # Create DTO
        return NLPResultDTO(
            sentiment_score=sentiment_score,
            confidence=confidence,
            emotions=emotions_aggregate,
            key_phrases=unique_phrases,
            emotional_trajectory=emotional_trajectory,
            language_insights=language_insights,
            analyzed_count=len(reviews),
            timestamp=datetime.now(),
        )

    def _calculate_polarity(self, text: str) -> float:
        """Calculate sentiment polarity of text (-1 to 1).
        
        Uses TextBlob for polarity analysis. Falls back to simple
        positive/negative word counting if TextBlob unavailable.
        
        Args:
            text: Review text to analyze.
        
        Returns:
            Polarity score from -1 (negative) to 1 (positive).
        """
        if not text:
            return 0.0
        
        try:
            from textblob import TextBlob
            return TextBlob(text).sentiment.polarity
        except ImportError:
            logger.warning("TextBlob not available, using fallback polarity")
            return self._fallback_polarity_calculation(text)
        except Exception as e:
            logger.warning(f"Polarity calculation failed: {e}, using fallback")
            return self._fallback_polarity_calculation(text)

    def _fallback_polarity_calculation(self, text: str) -> float:
        """Fallback polarity calculation using word counting.
        
        Args:
            text: Text to analyze.
        
        Returns:
            Polarity score.
        """
        text_lower = text.lower()
        
        positive_words = {
            "great", "excellent", "amazing", "wonderful", "fantastic",
            "good", "nice", "best", "awesome", "perfect", "love",
            "perfect", "brilliant", "outstanding", "superb", "lovely",
        }
        negative_words = {
            "bad", "terrible", "awful", "horrible", "worst", "hate",
            "poor", "disappointing", "disgusting", "ugly", "pathetic",
            "mediocre", "dreadful", "atrocious", "abysmal", "rubbish",
        }
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        total = positive_count + negative_count
        if total == 0:
            return 0.0
        
        return (positive_count - negative_count) / total

    def _extract_emotions(self, text: str) -> Dict[str, float]:
        """Extract emotions and their intensities from text.
        
        Args:
            text: Review text to analyze.
        
        Returns:
            Dictionary mapping emotion names to intensity (0-1).
        """
        emotions: Dict[str, float] = {
            "joy": 0.0,
            "sadness": 0.0,
            "anger": 0.0,
            "surprise": 0.0,
            "trust": 0.0,
            "fear": 0.0,
        }
        
        # Emotion keywords mapping
        emotion_keywords = {
            "joy": ["happy", "glad", "delighted", "pleased", "satisfied", "love"],
            "sadness": ["sad", "unhappy", "disappointed", "upset", "frustrated"],
            "anger": ["angry", "furious", "mad", "annoyed", "irritated", "hate"],
            "surprise": ["surprised", "shocked", "amazed", "astonished", "wow"],
            "trust": ["confident", "trust", "assured", "certain", "believe"],
            "fear": ["afraid", "scared", "worried", "concerned", "anxious"],
        }
        
        text_lower = text.lower()
        total_words = len(text_lower.split())
        
        for emotion, keywords in emotion_keywords.items():
            keyword_count = sum(1 for kw in keywords if kw in text_lower)
            if total_words > 0:
                emotions[emotion] = min(keyword_count / total_words, 1.0)
        
        return emotions

    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases from review text.
        
        Args:
            text: Review text to analyze.
        
        Returns:
            List of extracted key phrases.
        """
        if not text:
            return []
        
        # Simple extraction: capitalize and return multi-word sequences
        words = text.split()
        phrases = []
        
        # Extract 2-word and 3-word phrases (simple approach)
        for i in range(len(words) - 1):
            if len(words[i]) > 3:  # Skip short words
                phrase_2 = f"{words[i]} {words[i+1]}"
                phrases.append(phrase_2)
                
                if i + 2 < len(words) and len(words[i+2]) > 3:
                    phrase_3 = f"{words[i]} {words[i+1]} {words[i+2]}"
                    phrases.append(phrase_3)
        
        return phrases

    def _extract_language_insights(
        self,
        reviews: List[Any],
    ) -> Dict[str, Any]:
        """Extract language patterns and insights from reviews.
        
        Args:
            reviews: List of review objects to analyze.
        
        Returns:
            Dictionary with language insights.
        """
        if not reviews:
            return {}
        
        texts = [getattr(r, "text", "") for r in reviews if hasattr(r, "text")]
        
        avg_review_length = (
            sum(len(t.split()) for t in texts) / len(texts) if texts else 0
        )
        
        # Calculate text diversity (rough estimate)
        unique_words = set()
        for text in texts:
            unique_words.update(text.lower().split())
        
        diversity_ratio = len(unique_words) / sum(len(t.split()) for t in texts) if texts else 0
        
        return {
            "average_review_length": int(avg_review_length),
            "text_diversity_ratio": round(diversity_ratio, 2),
            "review_count": len(reviews),
        }

    def _calculate_trend_linear_regression(
        self,
        place_id: str,
        reviews: List[Any],
    ) -> TrendDTO:
        """Calculate sentiment trend using linear regression.
        
        Args:
            place_id: Place identifier.
            reviews: List of review objects sorted by date.
        
        Returns:
            TrendDTO with direction, strength, and change percent.
        """
        if len(reviews) < 2:
            return TrendDTO(direction="stable", strength=0.0, change_percent=0.0)
        
        # Calculate sentiment for each review
        sentiments = []
        for review in reviews:
            text = getattr(review, "text", "")
            rating = getattr(review, "rating", 3.0)
            polarity_normalized = (self._calculate_polarity(text) + 1) / 2
            rating_normalized = min(rating / 5.0, 1.0)
            sentiment = (polarity_normalized * 0.6) + (rating_normalized * 0.4)
            sentiments.append(sentiment)
        
        # Linear regression: calculate slope
        n = len(sentiments)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(sentiments) / n
        
        numerator = sum((x[i] - x_mean) * (sentiments[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0.0
        
        # Determine direction and strength
        if slope > 0.01:
            direction = "upward"
        elif slope < -0.01:
            direction = "downward"
        else:
            direction = "stable"
        
        strength = min(abs(slope) * 10, 1.0)  # Scale to 0-1
        
        # Calculate percentage change
        first_sentiment = sentiments[0]
        last_sentiment = sentiments[-1]
        change_percent = (
            ((last_sentiment - first_sentiment) / abs(first_sentiment))
            * 100
            if first_sentiment != 0
            else 0.0
        )
        
        return TrendDTO(
            direction=direction,
            strength=strength,
            change_percent=change_percent,
        )

    def _generate_cache_key(self, *args: Any) -> str:
        """Generate deterministic cache key from arguments.
        
        Args:
            *args: Variable arguments to include in key.
        
        Returns:
            Cache key string.
        """
        return "_".join(str(arg) for arg in args)

    def _register_invalidation_pattern(self, pattern: str) -> None:
        """Register cache invalidation pattern.
        
        Args:
            pattern: Pattern to use for invalidation (e.g., "sentiment_*").
        """
        # Pattern registered but not immediately invalidated
        # Actual invalidation happens on data change events
        logger.debug(f"Registered invalidation pattern: {pattern}")


__all__ = ["NLPService"]

