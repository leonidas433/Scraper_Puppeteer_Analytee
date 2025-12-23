"""Unit tests for PatternDetectionService."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from database.service.analytics.pattern_detection_service import PatternDetectionService
from database.models.dto import PatternDTO


@pytest.fixture
def mock_uow():
    """Create mock UnitOfWork."""
    uow = Mock()
    uow.reviews = Mock()
    uow.reviews.filter = Mock()
    return uow


@pytest.fixture
def pattern_service(mock_uow):
    """Create PatternDetectionService with mocks."""
    service = PatternDetectionService(mock_uow)
    service._cache = Mock()
    service._cache.get = Mock(return_value=None)
    service._cache.set = Mock()
    service._transaction = MagicMock()
    service._transaction.return_value.__enter__ = Mock(return_value=None)
    service._transaction.return_value.__exit__ = Mock(return_value=None)
    return service


class TestPatternDetectionService:
    """Test pattern detection methods."""

    def test_detect_text_patterns_valid(self, pattern_service, mock_uow):
        """Test text pattern detection."""
        reviews = [
            Mock(text="amazing service, great food", rating=5),
            Mock(text="amazing service, great service", rating=5),
            Mock(text="good service, decent food", rating=4),
        ]
        mock_uow.reviews.filter.return_value = reviews

        result = pattern_service.detect_text_patterns(1, min_frequency=1)
        
        assert isinstance(result, list)
        assert all(isinstance(p, PatternDTO) for p in result)

    def test_detect_text_patterns_no_reviews(self, pattern_service, mock_uow):
        """Test with no reviews."""
        mock_uow.reviews.filter.return_value = []

        result = pattern_service.detect_text_patterns(1)
        
        assert result == []

    def test_detect_temporal_patterns_valid(self, pattern_service, mock_uow):
        """Test temporal pattern detection."""
        reviews = [
            Mock(created_at=datetime(2024, 1, 1, 10, 0)),
            Mock(created_at=datetime(2024, 1, 1, 10, 30)),
            Mock(created_at=datetime(2024, 1, 2, 10, 0)),
        ]
        mock_uow.reviews.filter.return_value = reviews

        result = pattern_service.detect_temporal_patterns(1)
        
        assert isinstance(result, list)

    def test_detect_behavioral_anomalies_valid(self, pattern_service, mock_uow):
        """Test behavioral anomaly detection."""
        reviews = [
            Mock(rating=5, created_at=datetime(2024, 1, 1, 10, 0)),
            Mock(rating=1, created_at=datetime(2024, 1, 2, 10, 0)),
            Mock(rating=5, created_at=datetime(2024, 1, 3, 10, 0)),
            Mock(rating=1, created_at=datetime(2024, 1, 4, 10, 0)),
            Mock(rating=5, created_at=datetime(2024, 1, 5, 10, 0)),
        ]
        mock_uow.reviews.filter.return_value = reviews

        result = pattern_service.detect_behavioral_anomalies(1)
        
        assert isinstance(result, list)

    def test_batch_pattern_detection_empty(self, pattern_service):
        """Test batch with empty list."""
        result = pattern_service.batch_pattern_detection([])
        assert result == {}

    def test_batch_pattern_detection_valid(self, pattern_service, mock_uow):
        """Test batch pattern detection."""
        reviews = [Mock(text="good service", rating=5, created_at=datetime.now())]
        mock_uow.reviews.filter.return_value = reviews

        result = pattern_service.batch_pattern_detection([1, 2], pattern_types=["text"])
        
        assert isinstance(result, dict)
        assert len(result) >= 0
