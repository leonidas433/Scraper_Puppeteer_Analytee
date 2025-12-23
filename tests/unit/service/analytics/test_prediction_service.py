"""Unit tests for PredictionService.

Tests cover:
    - Sentiment forecasting with valid inputs
    - Parameter validation
    - Anomaly detection
    - Batch forecasting
    - Cache behavior
    - Error handling
    - ARIMA and fallback algorithms
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from typing import List, Tuple, Any

from database.service.analytics.prediction_service import PredictionService
from database.service.base import ServiceException, ValidationException
from database.service.dto import ForecastDTO, AnomalyDTO, DateRangeDTO
from tests.fixtures.dto_factory import MockUnitOfWork


class TestPredictionServiceForecasting:
    """Test sentiment forecasting functionality."""

    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.mock_uow = MockUnitOfWork()
        self.service = PredictionService(self.mock_uow)

    def test_forecast_sentiment_valid_input(self) -> None:
        """Test forecasting with valid parameters."""
        # Arrange
        place_id = "place_forecast"
        mock_reviews = [
            Mock(
                text=f"Review {i}",
                rating=4.0,
                created_at=date.today() - timedelta(days=90 - i),
            )
            for i in range(20)  # 20 reviews over 90 days
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        result = self.service.forecast_sentiment(
            place_id, days_ahead=30, confidence=0.95
        )
        
        # Assert
        assert isinstance(result, ForecastDTO)
        assert len(result.predictions) == 30
        assert len(result.lower_bound) == 30
        assert len(result.upper_bound) == 30
        assert result.model_type in ["ARIMA", "ExponentialSmoothing"]
        assert result.rmse >= 0
        assert result.mape >= 0

    def test_forecast_sentiment_invalid_days_ahead(self) -> None:
        """Test forecasting rejects invalid days_ahead."""
        # Act & Assert
        with pytest.raises(ValidationException):
            self.service.forecast_sentiment("place_123", days_ahead=0)  # Too small
        
        with pytest.raises(ValidationException):
            self.service.forecast_sentiment("place_123", days_ahead=400)  # Too large

    def test_forecast_sentiment_invalid_confidence(self) -> None:
        """Test forecasting rejects invalid confidence level."""
        # Act & Assert
        with pytest.raises(ValidationException):
            self.service.forecast_sentiment("place_123", confidence=0.5)  # Too low
        
        with pytest.raises(ValidationException):
            self.service.forecast_sentiment("place_123", confidence=1.5)  # Too high

    def test_forecast_sentiment_insufficient_historical_data(self) -> None:
        """Test forecasting requires minimum historical data."""
        # Arrange
        place_id = "place_short_history"
        mock_reviews = [Mock(text="Only 5", rating=3.0) for _ in range(5)]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            self.service.forecast_sentiment(place_id)
        
        assert "INSUFFICIENT" in exc_info.value.error_code

    def test_forecast_sentiment_predictions_are_tuples(self) -> None:
        """Test forecast predictions are (date, value) tuples."""
        # Arrange
        place_id = "place_pred_format"
        mock_reviews = [
            Mock(
                text=f"Review {i}",
                rating=4.0,
                created_at=date.today() - timedelta(days=90 - i),
            )
            for i in range(20)
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        result = self.service.forecast_sentiment(place_id, days_ahead=7)
        
        # Assert
        assert len(result.predictions) == 7
        for pred_date, pred_value in result.predictions:
            assert isinstance(pred_date, date) or isinstance(pred_date, datetime)
            assert isinstance(pred_value, (int, float))
            assert -1.0 <= pred_value <= 1.0

    def test_forecast_sentiment_cache_hit(self) -> None:
        """Test forecast caching behavior."""
        # Arrange
        place_id = "place_cached_forecast"
        mock_reviews = [
            Mock(
                text=f"Review {i}",
                rating=4.0,
                created_at=date.today() - timedelta(days=90 - i),
            )
            for i in range(20)
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act - first call
        result1 = self.service.forecast_sentiment(
            place_id, days_ahead=30
        )
        
        # Second call should hit cache
        result2 = self.service.forecast_sentiment(
            place_id, days_ahead=30
        )
        
        # Assert - should only fetch once
        assert self.mock_uow.reviews.get_reviews_for_place.call_count == 1
        assert result1.predictions == result2.predictions


class TestPredictionServiceAnomalyDetection:
    """Test anomaly detection functionality."""

    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.mock_uow = MockUnitOfWork()
        self.service = PredictionService(self.mock_uow)

    def test_detect_anomalies_valid_input(self) -> None:
        """Test anomaly detection with valid input."""
        # Arrange
        place_id = "place_anomalies"
        # Create time-series with one anomaly
        mock_reviews = [
            Mock(text="Good", rating=4.0, created_at=date.today() - timedelta(days=i))
            for i in range(90, 10, -7)  # Multiple reviews over 90 days
        ]
        # Add one extreme review
        mock_reviews.insert(
            5, Mock(text="EXTREMELY NEGATIVE!!!", rating=1.0, created_at=date.today() - timedelta(days=30))
        )
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        anomalies = self.service.detect_anomalies(place_id, sensitivity=0.95)
        
        # Assert
        assert isinstance(anomalies, list)
        for anomaly in anomalies:
            assert isinstance(anomaly, AnomalyDTO)
            assert 0.0 <= anomaly.severity <= 1.0
            assert isinstance(anomaly.description, str)
            assert isinstance(anomaly.suggested_action, str)

    def test_detect_anomalies_invalid_sensitivity(self) -> None:
        """Test anomaly detection rejects invalid sensitivity."""
        # Act & Assert
        with pytest.raises(ValidationException):
            self.service.detect_anomalies("place_123", sensitivity=0.5)  # Too low
        
        with pytest.raises(ValidationException):
            self.service.detect_anomalies("place_123", sensitivity=1.5)  # Too high

    def test_detect_anomalies_insufficient_data(self) -> None:
        """Test anomaly detection requires minimum data."""
        # Arrange
        place_id = "place_anom_short"
        mock_reviews = [
            Mock(text="Only 2", rating=3.0),
            Mock(text="Reviews", rating=3.0),
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            self.service.detect_anomalies(place_id)
        
        assert "INSUFFICIENT" in exc_info.value.error_code

    def test_detect_anomalies_returns_severity(self) -> None:
        """Test detected anomalies include severity scores."""
        # Arrange
        place_id = "place_severity"
        # Create baseline reviews
        mock_reviews = [
            Mock(text=f"Review {i}", rating=4.0, created_at=date.today() - timedelta(days=i))
            for i in range(50, 0, -5)
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        anomalies = self.service.detect_anomalies(place_id)
        
        # Assert
        for anomaly in anomalies:
            assert 0.0 <= anomaly.severity <= 1.0
            assert anomaly.severity > 0  # If detected, has some severity

    def test_detect_anomalies_sorted_by_severity(self) -> None:
        """Test anomalies are sorted by severity (descending)."""
        # Arrange
        place_id = "place_sort_severity"
        mock_reviews = [
            Mock(text=f"Review {i}", rating=4.0, created_at=date.today() - timedelta(days=i))
            for i in range(50, 0, -5)
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        anomalies = self.service.detect_anomalies(place_id)
        
        # Assert
        if len(anomalies) > 1:
            for i in range(len(anomalies) - 1):
                assert anomalies[i].severity >= anomalies[i + 1].severity


class TestPredictionServiceBatch:
    """Test batch forecasting."""

    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.mock_uow = MockUnitOfWork()
        self.service = PredictionService(self.mock_uow)

    def test_batch_forecast_multiple_places(self) -> None:
        """Test batch forecasting for multiple places."""
        # Arrange
        place_ids = ["place_batch_1", "place_batch_2", "place_batch_3"]
        mock_reviews = [
            Mock(
                text=f"Review {i}",
                rating=4.0,
                created_at=date.today() - timedelta(days=90 - i),
            )
            for i in range(20)
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        results = self.service.batch_forecast(place_ids, days_ahead=30)
        
        # Assert
        assert isinstance(results, dict)
        assert len(results) > 0  # At least some succeeded
        for place_id, forecast in results.items():
            assert isinstance(forecast, ForecastDTO)

    def test_batch_forecast_empty_list(self) -> None:
        """Test batch forecasting rejects empty place list."""
        # Act & Assert
        with pytest.raises(ValidationException):
            self.service.batch_forecast([])

    def test_batch_forecast_graceful_failure_handling(self) -> None:
        """Test batch forecast handles partial failures gracefully."""
        # Arrange
        place_ids = ["place_ok", "place_fail", "place_ok2"]
        call_count = [0]
        
        def mock_fetch(place_id, *args, **kwargs):
            call_count[0] += 1
            if place_id == "place_fail":
                return []  # Trigger failure
            return [
                Mock(
                    text=f"Review {i}",
                    rating=4.0,
                    created_at=date.today() - timedelta(days=90 - i),
                )
                for i in range(20)
            ]
        
        self.mock_uow.reviews.get_reviews_for_place.side_effect = mock_fetch
        
        # Act
        results = self.service.batch_forecast(place_ids)
        
        # Assert - should have some results despite one failure
        assert len(results) >= 1  # At least one place succeeded
        assert len(results) <= 2  # At most 2 (one failed)


class TestPredictionServiceTransactions:
    """Test transaction behavior."""

    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.mock_uow = MockUnitOfWork()
        self.service = PredictionService(self.mock_uow)

    def test_forecast_within_transaction(self) -> None:
        """Test forecast operates within transaction."""
        # Arrange
        place_id = "place_tx_forecast"
        mock_reviews = [
            Mock(
                text=f"Review {i}",
                rating=4.0,
                created_at=date.today() - timedelta(days=90 - i),
            )
            for i in range(20)
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        result = self.service.forecast_sentiment(place_id)
        
        # Assert
        assert self.mock_uow.committed is True

    def test_anomaly_detection_within_transaction(self) -> None:
        """Test anomaly detection operates within transaction."""
        # Arrange
        place_id = "place_tx_anomaly"
        mock_reviews = [
            Mock(
                text=f"Review {i}",
                rating=4.0,
                created_at=date.today() - timedelta(days=i),
            )
            for i in range(50, 0, -5)
        ]
        self.mock_uow.reviews.get_reviews_for_place.return_value = mock_reviews
        
        # Act
        result = self.service.detect_anomalies(place_id)
        
        # Assert
        assert self.mock_uow.committed is True


class TestPredictionServiceErrorHandling:
    """Test error handling and context."""

    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.mock_uow = MockUnitOfWork()
        self.service = PredictionService(self.mock_uow)

    def test_forecast_exception_includes_context(self) -> None:
        """Test forecast exceptions include error context."""
        # Arrange
        place_id = "place_error_forecast"
        self.mock_uow.reviews.get_reviews_for_place.side_effect = Exception("DB error")
        
        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            self.service.forecast_sentiment(place_id)
        
        assert exc_info.value.context is not None
        assert "place_id" in exc_info.value.context

    def test_anomaly_exception_includes_context(self) -> None:
        """Test anomaly exceptions include error context."""
        # Arrange
        place_id = "place_error_anomaly"
        self.mock_uow.reviews.get_reviews_for_place.side_effect = Exception("DB error")
        
        # Act & Assert
        with pytest.raises(ServiceException) as exc_info:
            self.service.detect_anomalies(place_id)
        
        assert exc_info.value.context is not None


__all__ = [
    "TestPredictionServiceForecasting",
    "TestPredictionServiceAnomalyDetection",
    "TestPredictionServiceBatch",
    "TestPredictionServiceTransactions",
    "TestPredictionServiceErrorHandling",
]
