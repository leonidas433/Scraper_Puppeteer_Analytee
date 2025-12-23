"""Tests for analytics services.

Includes unit tests for:
    - NLPService (sentiment analysis, emotions, trends)
    - PredictionService (forecasting, anomalies)
    
And integration tests demonstrating service interactions.
"""

from tests.unit.service.analytics.test_nlp_service import *
from tests.unit.service.analytics.test_prediction_service import *

__all__ = [
    "TestNLPServiceSentimentAnalysis",
    "TestNLPServiceTrend",
    "TestNLPServiceBatch",
    "TestNLPServiceTransactions",
    "TestNLPServiceErrorHandling",
    "TestPredictionServiceForecasting",
    "TestPredictionServiceAnomalyDetection",
    "TestPredictionServiceBatch",
    "TestPredictionServiceTransactions",
    "TestPredictionServiceErrorHandling",
]
