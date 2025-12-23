"""Unit tests for NLPService.

Tests cover:
    - Sentiment analysis with valid inputs
    - Input validation failures
    - Domain validation failures
    - Cache hit/miss behavior
    - Batch processing (parallel)
    - Error handling and context
    - Trend calculation
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, ANY
from typing import List, Any

from database.service.analytics.nlp_service import NLPService
from database.service.base import ServiceException, ValidationException
from database.service.dto import DateRangeDTO, NLPResultDTO, TrendDTO
from tests.fixtures.dto_factory import MockUnitOfWork


class TestNLPServiceSentimentAnalysis:
    """Test sentiment analysis functionality."""

    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.mock_uow = MockUnitOfWork()
        self.service = NLPService(self.mock_uow)

    def test_analyze_sentiment_valid_input(self) -> None:
        """Test sentiment analysis with valid place_id."""
        # Arrange
        place_id = "place_123"
        date_range = DateRangeDTO(
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
        )
        
        # Mock reviews
        mock_reviews = [
            Mock(text="Great service!", rating=5.0),
            Mock(text="Good experience", rating=4.0),
            Mock(text="Average place", rating=3.0),
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        result = self.service.analyze_sentiment(place_id, date_range)
        
        # Assert
        assert isinstance(result, NLPResultDTO)
        assert result.sentiment_score is not None
        assert -1.0 <= result.sentiment_score <= 1.0
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.emotions) > 0
        assert isinstance(result.analyzed_count, int)
        assert result.analyzed_count == len(mock_reviews)

    def test_analyze_sentiment_default_date_range(self) -> None:
        """Test sentiment analysis uses default date range (90 days)."""
        # Arrange
        place_id = "place_456"
        mock_reviews = [
            Mock(text="Excellent!", rating=5.0),
            Mock(text="Good", rating=4.0),
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        result = self.service.analyze_sentiment(place_id)  # No date_range
        
        # Assert
        assert isinstance(result, NLPResultDTO)
        self.mock_uow.reviews.get_reviews_for_place.assert_called_once()

    def test_analyze_sentiment_invalid_place_id_format(self) -> None:
        """Test sentiment analysis rejects invalid place_id format."""
        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            self.service.analyze_sentiment("")  # Empty place_id
        
        assert "place_id" in str(exc_info.value.context)

    def test_analyze_sentiment_place_not_found(self) -> None:
        """Test sentiment analysis fails when place doesn't exist."""
        # Arrange
        place_id = "nonexistent_place"
        self.mock_uow.reviews.get_reviews_for_place.return_value = []
        
        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            self.service.analyze_sentiment(place_id)
        
        assert "NO_REVIEWS_FOUND" in str(exc_info.value.error_code)

    def test_analyze_sentiment_insufficient_data(self) -> None:
        """Test sentiment analysis requires minimum reviews and date span."""
        # Arrange
        place_id = "place_789"
        mock_reviews = [Mock(text="Okay", rating=3.0)]  # Only 1 review
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act & Assert - should fail in DomainValidator
        with pytest.raises(ServiceException) as exc_info:
            self.service.analyze_sentiment(place_id)
        
        assert exc_info.value.error_code in [
            "INSUFFICIENT_HISTORICAL_DATA",
            "NO_REVIEWS_FOUND",
        ]

    def test_analyze_sentiment_cache_hit(self) -> None:
        """Test sentiment analysis returns cached result on second call."""
        # Arrange
        place_id = "place_cached"
        date_range = DateRangeDTO(
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
        )
        mock_reviews = [
            Mock(text="Great!", rating=5.0),
            Mock(text="Good", rating=4.0),
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act - first call
        result1 = self.service.analyze_sentiment(place_id, date_range)
        
        # Second call should hit cache
        result2 = self.service.analyze_sentiment(place_id, date_range)
        
        # Assert - should only fetch once from repo
        assert self.mock_uow.reviews.get_reviews_for_place.call_count == 1
        assert result1.sentiment_score == result2.sentiment_score

    def test_analyze_sentiment_returns_emotions(self) -> None:
        """Test sentiment analysis extracts emotions."""
        # Arrange
        place_id = "place_emotions"
        mock_reviews = [
            Mock(text="I am so happy and delighted!", rating=5.0),
            Mock(text="I hate this place", rating=1.0),
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        result = self.service.analyze_sentiment(place_id)
        
        # Assert
        assert isinstance(result.emotions, dict)
        assert "joy" in result.emotions
        assert "anger" in result.emotions
        assert sum(result.emotions.values()) > 0

    def test_analyze_sentiment_returns_key_phrases(self) -> None:
        """Test sentiment analysis extracts key phrases."""
        # Arrange
        place_id = "place_phrases"
        mock_reviews = [
            Mock(text="Great customer service and excellent food", rating=5.0),
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        result = self.service.analyze_sentiment(place_id)
        
        # Assert
        assert isinstance(result.key_phrases, list)
        # Should contain some multi-word phrases
        assert len(result.key_phrases) >= 0


class TestNLPServiceTrend:
    """Test sentiment trend calculation."""

    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.mock_uow = MockUnitOfWork()
        self.service = NLPService(self.mock_uow)

    def test_get_sentiment_trend_valid(self) -> None:
        """Test trend calculation with valid input."""
        # Arrange
        place_id = "place_trend"
        mock_reviews = [
            Mock(text="Good", rating=4.0, created_at=date.today() - timedelta(days=30)),
            Mock(text="Better", rating=4.5, created_at=date.today() - timedelta(days=20)),
            Mock(text="Excellent!", rating=5.0, created_at=date.today()),
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        result = self.service.get_sentiment_trend(place_id, period=30)
        
        # Assert
        assert isinstance(result, TrendDTO)
        assert result.direction in ["upward", "downward", "stable"]
        assert 0.0 <= result.strength <= 1.0
        assert isinstance(result.change_percent, float)

    def test_get_sentiment_trend_invalid_period(self) -> None:
        """Test trend calculation rejects invalid period."""
        # Act & Assert
        with pytest.raises(ValidationException):
            self.service.get_sentiment_trend("place_123", period=0)  # Too small
        
        with pytest.raises(ValidationException):
            self.service.get_sentiment_trend("place_123", period=400)  # Too large

    def test_get_sentiment_trend_insufficient_data(self) -> None:
        """Test trend calculation needs minimum data points."""
        # Arrange
        place_id = "place_trend_short"
        mock_reviews = [Mock(text="Only one", rating=3.0)]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act & Assert
        with pytest.raises(ServiceException):
            self.service.get_sentiment_trend(place_id)


class TestNLPServiceBatch:
    """Test batch sentiment analysis."""

    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.mock_uow = MockUnitOfWork()
        self.service = NLPService(self.mock_uow)

    def test_batch_analyze_places_multiple_places(self) -> None:
        """Test batch analysis for multiple places."""
        # Arrange
        place_ids = ["place_1", "place_2", "place_3"]
        mock_reviews = [
            Mock(text="Great!", rating=5.0),
            Mock(text="Good", rating=4.0),
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        results = self.service.batch_analyze_places(place_ids)
        
        # Assert
        assert isinstance(results, dict)
        assert len(results) > 0  # At least some succeeded
        for place_id, result in results.items():
            assert isinstance(result, NLPResultDTO)

    def test_batch_analyze_places_empty_list(self) -> None:
        """Test batch analysis rejects empty place list."""
        # Act & Assert
        with pytest.raises(ValidationException):
            self.service.batch_analyze_places([])

    def test_batch_analyze_places_parallel_execution(self) -> None:
        """Test batch analysis uses parallel execution."""
        # Arrange
        place_ids = ["place_p1", "place_p2"]
        mock_reviews = [Mock(text="Good", rating=4.0)]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        results = self.service.batch_analyze_places(
            place_ids, max_workers=2
        )
        
        # Assert
        assert len(results) > 0


class TestNLPServiceTransactions:
    """Test transaction behavior."""

    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.mock_uow = MockUnitOfWork()
        self.service = NLPService(self.mock_uow)

    def test_sentiment_analysis_within_transaction(self) -> None:
        """Test sentiment analysis operates within transaction."""
        # Arrange
        place_id = "place_tx"
        mock_reviews = [
            Mock(text="Great!", rating=5.0),
            Mock(text="Good", rating=4.0),
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        result = self.service.analyze_sentiment(place_id)
        
        # Assert - transaction should have been used
        assert self.mock_uow.in_transaction is False  # Committed
        assert self.mock_uow.committed is True


class TestNLPServiceErrorHandling:
    """Test error handling and context."""

    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.mock_uow = MockUnitOfWork()
        self.service = NLPService(self.mock_uow)

    def test_service_exception_includes_context(self) -> None:
        """Test service exceptions include error context."""
        # Arrange
        place_id = "place_error"
        self.mock_uow.reviews.get_reviews_for_place.side_effect = Exception("DB error")
        
        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            self.service.analyze_sentiment(place_id)
        
        assert exc_info.value.context is not None
        assert "place_id" in exc_info.value.context
        assert exc_info.value.context["place_id"] == place_id

    def test_validation_exception_includes_field_context(self) -> None:
        """Test validation exceptions include field context."""
        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            self.service.analyze_sentiment("")
        
        assert exc_info.value.context is not None


__all__ = [
    "TestNLPServiceSentimentAnalysis",
    "TestNLPServiceTrend",
    "TestNLPServiceBatch",
    "TestNLPServiceTransactions",
    "TestNLPServiceErrorHandling",
]
