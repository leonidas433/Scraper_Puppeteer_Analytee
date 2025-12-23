"""Unit tests for ClusteringService."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from database.service.analytics.clustering_service import ClusteringService
from database.models.dto import ClusterResultDTO


@pytest.fixture
def mock_uow():
    """Create mock UnitOfWork."""
    uow = Mock()
    uow.places = Mock()
    uow.places.get = Mock()
    return uow


@pytest.fixture
def clustering_service(mock_uow):
    """Create ClusteringService with mocks."""
    service = ClusteringService(mock_uow)
    service._cache = Mock()
    service._cache.get = Mock(return_value=None)
    service._cache.set = Mock()
    service._transaction = MagicMock()
    service._transaction.return_value.__enter__ = Mock(return_value=None)
    service._transaction.return_value.__exit__ = Mock(return_value=None)
    return service


class TestClusteringServiceAnalysis:
    """Test clustering methods."""

    def test_cluster_places_valid(self, clustering_service, mock_uow):
        """Test valid clustering."""
        places = [
            Mock(id=1, avg_rating=4.5, review_count=100),
            Mock(id=2, avg_rating=4.3, review_count=95),
            Mock(id=3, avg_rating=2.1, review_count=20),
        ]
        mock_uow.places.get.side_effect = places

        result = clustering_service.cluster_places([1, 2, 3], n_clusters=2)
        
        assert isinstance(result, ClusterResultDTO)
        assert result.n_clusters == 2
        assert len(result.clusters) > 0

    def test_cluster_places_insufficient_places(self, clustering_service):
        """Test with insufficient places."""
        with pytest.raises(ValueError):
            clustering_service.cluster_places([1], n_clusters=3)

    def test_cluster_places_empty(self, clustering_service):
        """Test with empty list."""
        with pytest.raises(ValueError):
            clustering_service.cluster_places([], n_clusters=3)

    def test_get_cluster_for_place(self, clustering_service, mock_uow):
        """Test cluster assignment for single place."""
        places = [
            Mock(id=1, avg_rating=4.5, review_count=100),
            Mock(id=2, avg_rating=4.3, review_count=95),
            Mock(id=3, avg_rating=2.1, review_count=20),
        ]
        mock_uow.places.get.side_effect = places

        result = clustering_service.get_cluster_for_place(3, [1, 2], n_clusters=2)
        
        assert isinstance(result, int)
        assert result >= -1

    def test_batch_cluster_analysis(self, clustering_service, mock_uow):
        """Test batch clustering."""
        places_group1 = [
            Mock(id=1, avg_rating=4.5, review_count=100),
            Mock(id=2, avg_rating=4.3, review_count=95),
            Mock(id=3, avg_rating=2.1, review_count=20),
        ]
        
        mock_uow.places.get.side_effect = places_group1 * 3

        groups = {
            "group_a": [1, 2, 3],
            "group_b": [1, 2, 3],
        }

        result = clustering_service.batch_cluster_analysis(groups, n_clusters=2)
        
        assert isinstance(result, dict)
        assert len(result) >= 0
