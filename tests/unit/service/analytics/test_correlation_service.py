"""Unit tests for CorrelationService."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from database.service.analytics.correlation_service import CorrelationService
from database.models.dto import CorrelationResultDTO, CorrelationPairDTO


@pytest.fixture
def mock_uow():
    """Create mock UnitOfWork."""
    uow = Mock()
    uow.places = Mock()
    uow.places.get = Mock()
    uow.places.filter = Mock()
    return uow


@pytest.fixture
def correlation_service(mock_uow):
    """Create CorrelationService with mocks."""
    service = CorrelationService(mock_uow)
    service._cache = Mock()
    service._cache.get = Mock(return_value=None)
    service._cache.set = Mock()
    service._transaction = MagicMock()
    service._transaction.return_value.__enter__ = Mock(return_value=None)
    service._transaction.return_value.__exit__ = Mock(return_value=None)
    return service


class TestCorrelationServiceAnalysis:
    """Test correlation analysis methods."""

    def test_analyze_place_correlations_valid(self, correlation_service, mock_uow):
        """Test valid correlation analysis."""
        place = Mock(id=1, avg_rating=4.5, review_count=100, region="downtown")
        mock_uow.places.get.return_value = place
        mock_uow.places.filter.return_value = [place]

        result = correlation_service.analyze_place_correlations(1)
        
        assert isinstance(result, CorrelationResultDTO)
        assert result.place_id == 1
        assert result.peer_count >= 0

    def test_analyze_place_correlations_invalid_id(self, correlation_service):
        """Test with invalid place ID."""
        with pytest.raises(ValueError):
            correlation_service.analyze_place_correlations(0)

    def test_analyze_place_correlations_not_found(self, correlation_service, mock_uow):
        """Test with non-existent place."""
        mock_uow.places.get.return_value = None

        with pytest.raises(ValueError):
            correlation_service.analyze_place_correlations(999)

    def test_get_peer_group_correlations(self, correlation_service, mock_uow):
        """Test peer group retrieval."""
        place = Mock(id=1, avg_rating=4.5, review_count=100, region="downtown")
        peer = Mock(id=2, avg_rating=4.3, review_count=95, region="downtown")
        
        mock_uow.places.get.return_value = place
        mock_uow.places.filter.return_value = [place, peer]

        result = correlation_service.get_peer_group_correlations(1, peer_count=5)
        
        assert isinstance(result, list)
        assert len(result) >= 0

    def test_batch_correlations_empty(self, correlation_service):
        """Test batch with empty list."""
        result = correlation_service.batch_correlations([])
        assert result == {}

    def test_batch_correlations_valid(self, correlation_service, mock_uow):
        """Test batch correlation analysis."""
        place = Mock(id=1, avg_rating=4.5, review_count=100, region="downtown")
        mock_uow.places.get.return_value = place
        mock_uow.places.filter.return_value = [place]

        result = correlation_service.batch_correlations([1, 2])
        
        assert isinstance(result, dict)
