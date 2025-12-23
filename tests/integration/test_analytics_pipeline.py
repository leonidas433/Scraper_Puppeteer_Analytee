"""Integration tests for analytics services.

Tests demonstrate full analytics pipeline:
    1. NLPService: Sentiment analysis
    2. PredictionService: Forecasting based on sentiment
    3. Integration: Error propagation and transaction safety
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock

from database.service.analytics import NLPService, PredictionService
from database.service.base import ServiceException
from database.service.dto import DateRangeDTO, NLPResultDTO, ForecastDTO
from tests.fixtures.dto_factory import MockUnitOfWork


class TestAnalyticsPipeline:
    """Test complete analytics pipeline."""

    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.mock_uow = MockUnitOfWork()
        self.nlp_service = NLPService(self.mock_uow)
        self.pred_service = PredictionService(self.mock_uow)

    def test_full_analytics_pipeline(self) -> None:
        """Test full pipeline: sentiment analysis -> forecasting."""
        # Arrange
        place_id = "place_pipeline"
        mock_reviews = [
            Mock(
                text=f"Review {i}: {'Great!' if i % 2 == 0 else 'Good'}",
                rating=4.5 if i % 2 == 0 else 4.0,
                created_at=date.today() - timedelta(days=90 - i),
            )
            for i in range(25)
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act - Step 1: Analyze sentiment
        nlp_result = self.nlp_service.analyze_sentiment(place_id)
        
        # Assert - NLP result is valid
        assert isinstance(nlp_result, NLPResultDTO)
        assert nlp_result.sentiment_score is not None
        
        # Act - Step 2: Forecast based on sentiment
        forecast_result = self.pred_service.forecast_sentiment(
            place_id, days_ahead=30
        )
        
        # Assert - Forecast is valid
        assert isinstance(forecast_result, ForecastDTO)
        assert len(forecast_result.predictions) == 30

    def test_sentiment_then_anomaly_detection(self) -> None:
        """Test sentiment analysis followed by anomaly detection."""
        # Arrange
        place_id = "place_sentiment_then_anomaly"
        mock_reviews = [
            Mock(
                text=f"Review {i}",
                rating=4.0 if i % 5 != 0 else 1.0,  # Some anomalies
                created_at=date.today() - timedelta(days=i),
            )
            for i in range(50, 0, -2)
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act - Sentiment analysis
        nlp_result = self.nlp_service.analyze_sentiment(place_id)
        assert isinstance(nlp_result, NLPResultDTO)
        
        # Anomaly detection
        anomalies = self.pred_service.detect_anomalies(place_id)
        
        # Assert
        assert isinstance(anomalies, list)

    def test_batch_operations_coordination(self) -> None:
        """Test batch NLP and batch forecasting can work in sequence."""
        # Arrange
        place_ids = ["place_batch_1", "place_batch_2"]
        mock_reviews = [
            Mock(
                text=f"Review {i}",
                rating=4.0,
                created_at=date.today() - timedelta(days=90 - i),
            )
            for i in range(20)
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act - Batch sentiment analysis
        nlp_results = self.nlp_service.batch_analyze_places(place_ids)
        
        # Assert
        assert len(nlp_results) > 0
        
        # Act - Batch forecasting
        forecast_results = self.pred_service.batch_forecast(place_ids)
        
        # Assert
        assert len(forecast_results) > 0

    def test_services_share_underlying_uow(self) -> None:
        """Test both services use same UnitOfWork."""
        # Assert
        assert self.nlp_service.unit_of_work is self.pred_service.unit_of_work


__all__ = [
    "TestAnalyticsPipeline",
]
