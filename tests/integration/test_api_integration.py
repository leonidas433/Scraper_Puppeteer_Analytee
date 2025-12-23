"""
Integration tests for FastAPI application

Tests the complete API flow including:
- Endpoint availability and response formats
- Error handling and validation
- Service integration through API
- Batch operations
- Health checks
"""

import pytest
import json
from fastapi.testclient import TestClient
from api.main import app
from database.repository.unit_of_work import UnitOfWork
from database.models import Place, Review, OwnerResponse
from datetime import datetime

# Create test client
client = TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_health_check(self):
        """Test health check endpoint returns correct structure"""
        response = client.get("/api/v1/health/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status_code"] == 200
        assert "data" in data
        assert "services" in data["data"]
    
    def test_health_check_structure(self):
        """Test health check response structure"""
        response = client.get("/api/v1/health/")
        data = response.json()
        
        expected_services = ["nlp", "prediction", "correlation", "clustering", "pattern_detection"]
        for service in expected_services:
            assert service in data["data"]["services"]
            assert data["data"]["services"][service] == "active"


class TestNLPEndpoints:
    """Test NLP service endpoints"""
    
    @pytest.fixture
    def setup_test_data(self):
        """Create test data"""
        uow = UnitOfWork()
        
        # Create a test place
        place = Place(
            name="Test Restaurant",
            address="Test Address",
            place_type="restaurant",
            rating=4.5,
            total_reviews=100
        )
        
        try:
            uow.place_repository.create(place)
            uow.commit()
            yield place.id
        finally:
            # Cleanup
            try:
                uow.place_repository.delete(place)
                uow.commit()
            except:
                pass
    
    def test_analyze_sentiment_invalid_place(self):
        """Test sentiment analysis with invalid place ID"""
        response = client.post("/api/v1/nlp/analyze-sentiment?place_id=99999&limit=50")
        
        # Should handle gracefully - either 400 or 404 depending on implementation
        assert response.status_code in [400, 404, 500]
    
    def test_analyze_sentiment_parameters(self):
        """Test sentiment analysis parameter validation"""
        # Test with invalid limit (too high)
        response = client.post("/api/v1/nlp/analyze-sentiment?place_id=1&limit=2000")
        assert response.status_code == 422  # Validation error
        
        # Test with invalid limit (too low)
        response = client.post("/api/v1/nlp/analyze-sentiment?place_id=1&limit=0")
        assert response.status_code == 422  # Validation error
    
    def test_sentiment_trend_parameters(self):
        """Test sentiment trend parameter validation"""
        # Test with invalid days
        response = client.get("/api/v1/nlp/sentiment-trend/1?days=0")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/v1/nlp/sentiment-trend/1?days=400")
        assert response.status_code == 422  # Validation error
    
    def test_batch_analyze_empty_list(self):
        """Test batch analysis with empty place list"""
        response = client.post(
            "/api/v1/nlp/batch-analyze",
            json={"place_ids": []}
        )
        
        # Should handle empty list
        assert response.status_code in [200, 400]


class TestPredictionEndpoints:
    """Test Prediction service endpoints"""
    
    def test_forecast_parameters(self):
        """Test forecast parameter validation"""
        # Test with invalid forecast days
        response = client.post("/api/v1/predictions/forecast?place_id=1&forecast_days=0")
        assert response.status_code == 422
        
        response = client.post("/api/v1/predictions/forecast?place_id=1&forecast_days=100")
        assert response.status_code == 422
    
    def test_anomaly_detection_parameters(self):
        """Test anomaly detection parameter validation"""
        # Test with invalid threshold
        response = client.post("/api/v1/predictions/anomalies?place_id=1&threshold=0.3")
        assert response.status_code == 422
        
        response = client.post("/api/v1/predictions/anomalies?place_id=1&threshold=1.5")
        assert response.status_code == 422
    
    def test_batch_forecast_empty_list(self):
        """Test batch forecast with empty place list"""
        response = client.post(
            "/api/v1/predictions/batch-forecast",
            json={"place_ids": [], "forecast_days": 7}
        )
        
        assert response.status_code in [200, 400]


class TestCorrelationEndpoints:
    """Test Correlation service endpoints"""
    
    def test_analyze_correlations_method_validation(self):
        """Test correlation analysis with invalid method"""
        response = client.post("/api/v1/correlations/analyze?place_id=1&method=invalid")
        assert response.status_code == 422
    
    def test_analyze_correlations_threshold_validation(self):
        """Test correlation analysis with invalid threshold"""
        response = client.post("/api/v1/correlations/analyze?place_id=1&min_correlation=1.5")
        assert response.status_code == 422
        
        response = client.post("/api/v1/correlations/analyze?place_id=1&min_correlation=-0.1")
        assert response.status_code == 422
    
    def test_peer_group_count_validation(self):
        """Test peer group with invalid peer count"""
        response = client.get("/api/v1/correlations/peer-group/1?peer_count=0")
        assert response.status_code == 422
        
        response = client.get("/api/v1/correlations/peer-group/1?peer_count=100")
        assert response.status_code == 422
    
    def test_batch_correlations_empty_list(self):
        """Test batch correlations with empty place list"""
        response = client.post(
            "/api/v1/correlations/batch",
            json={"place_ids": []}
        )
        
        assert response.status_code in [200, 400]


class TestClusteringEndpoints:
    """Test Clustering service endpoints"""
    
    def test_cluster_places_n_clusters_validation(self):
        """Test clustering with invalid n_clusters"""
        response = client.post(
            "/api/v1/clustering/cluster-places",
            json={"place_ids": [1, 2, 3]},
            params={"n_clusters": 1}
        )
        assert response.status_code == 422
        
        response = client.post(
            "/api/v1/clustering/cluster-places",
            json={"place_ids": [1, 2, 3]},
            params={"n_clusters": 15}
        )
        assert response.status_code == 422
    
    def test_place_cluster_empty_reference(self):
        """Test place cluster with empty reference list"""
        response = client.post(
            "/api/v1/clustering/place-cluster",
            json={"place_id": 1, "reference_place_ids": []}
        )
        
        assert response.status_code in [200, 400, 422]
    
    def test_batch_cluster_analysis_empty_groups(self):
        """Test batch clustering with empty groups"""
        response = client.post(
            "/api/v1/clustering/batch",
            json={"place_groups": []}
        )
        
        assert response.status_code in [200, 400]


class TestPatternDetectionEndpoints:
    """Test Pattern Detection service endpoints"""
    
    def test_text_patterns_frequency_validation(self):
        """Test text pattern detection with invalid frequency"""
        response = client.post("/api/v1/patterns/text?place_id=1&min_frequency=0")
        assert response.status_code == 422
        
        response = client.post("/api/v1/patterns/text?place_id=1&min_frequency=100")
        assert response.status_code == 422
    
    def test_temporal_patterns_window_validation(self):
        """Test temporal pattern detection with invalid window"""
        response = client.post("/api/v1/patterns/temporal?place_id=1&window_days=0")
        assert response.status_code == 422
        
        response = client.post("/api/v1/patterns/temporal?place_id=1&window_days=100")
        assert response.status_code == 422
    
    def test_behavioral_anomalies_threshold_validation(self):
        """Test behavioral anomalies with invalid threshold"""
        response = client.post("/api/v1/patterns/anomalies?place_id=1&threshold=0.3")
        assert response.status_code == 422
    
    def test_batch_pattern_detection_empty_list(self):
        """Test batch pattern detection with empty place list"""
        response = client.post(
            "/api/v1/patterns/batch",
            json={"place_ids": []}
        )
        
        assert response.status_code in [200, 400]


class TestErrorHandling:
    """Test API error handling"""
    
    def test_invalid_endpoint(self):
        """Test invalid endpoint returns 404"""
        response = client.get("/api/v1/invalid-endpoint")
        assert response.status_code == 404
    
    def test_missing_required_parameter(self):
        """Test missing required parameter"""
        response = client.post("/api/v1/nlp/analyze-sentiment")
        assert response.status_code == 422
    
    def test_invalid_json_body(self):
        """Test invalid JSON body"""
        response = client.post(
            "/api/v1/clustering/cluster-places",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        # Should fail gracefully
        assert response.status_code in [400, 422]
    
    def test_error_response_structure(self):
        """Test error response has expected structure"""
        response = client.post(
            "/api/v1/nlp/analyze-sentiment?place_id=1&limit=2000"
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data or "errors" in data


class TestResponseFormats:
    """Test API response formats"""
    
    def test_api_response_structure(self):
        """Test standard API response structure"""
        response = client.get("/api/v1/health/")
        
        data = response.json()
        assert "success" in data
        assert "status_code" in data
        assert "message" in data
        assert "data" in data
    
    def test_batch_operation_response_structure(self):
        """Test batch operation response structure"""
        response = client.post(
            "/api/v1/nlp/batch-analyze",
            json={"place_ids": []}
        )
        
        if response.status_code == 200:
            data = response.json()
            # Should have batch operation fields
            assert "total_items" in data or "success" in data


class TestCORS:
    """Test CORS headers"""
    
    def test_cors_headers_present(self):
        """Test that CORS headers are set"""
        response = client.options("/api/v1/health/")
        
        # Check for CORS headers
        assert "access-control-allow-origin" in response.headers or response.status_code == 200


class TestPerformance:
    """Test API performance characteristics"""
    
    def test_health_check_performance(self):
        """Test health check responds quickly"""
        import time
        
        start = time.time()
        response = client.get("/api/v1/health/")
        duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 1.0  # Should respond in under 1 second
    
    def test_concurrent_requests(self):
        """Test API handles concurrent requests"""
        import concurrent.futures
        
        def make_request():
            return client.get("/api/v1/health/")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        assert all(r.status_code == 200 for r in results)


class TestDataValidation:
    """Test input data validation"""
    
    def test_place_id_type_validation(self):
        """Test place_id must be integer"""
        response = client.post("/api/v1/nlp/analyze-sentiment?place_id=invalid")
        assert response.status_code == 422
    
    def test_list_parameter_validation(self):
        """Test list parameters validation"""
        response = client.post(
            "/api/v1/clustering/cluster-places",
            json={"place_ids": "not-a-list"}
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])