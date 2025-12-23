"""Prediction Service for forecasting and anomaly detection.

This service forecasts sentiment trends and detects anomalies using
statistical methods. It provides sentiment predictions with confidence
intervals and identifies unusual patterns in review data.

Key Features:
    - ARIMA-based sentiment forecasting with auto-parameter selection
    - Z-score anomaly detection with spike detection
    - Confidence interval calculation (95% by default)
    - TTL-based caching (24 hours)
    - Fallback to exponential smoothing if ARIMA fails
    - Batch forecasting with parallel execution
    - Comprehensive error context

Example:
    >>> from database.service.analytics import PredictionService
    >>> from database.repository.unit_of_work import UnitOfWork
    >>> uow = UnitOfWork(...)
    >>> pred_service = PredictionService(uow)
    >>> forecast = pred_service.forecast_sentiment(
    ...     place_id="place_123",
    ...     days_ahead=30,
    ...     confidence=0.95
    ... )
    >>> print(f"Predictions: {forecast.predictions}")
    >>> print(f"RMSE: {forecast.rmse}")
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Any, Optional
import logging
import statistics

from database.service.base import BaseService, ServiceException, ValidationException
from database.service.validation import (
    InputValidator,
    DomainValidator,
    CrossEntityValidator,
    BusinessRuleValidator,
)
from database.service.dto import (
    ForecastDTO,
    AnomalyDTO,
    DateRangeDTO,
    DTOTransformer,
)
from database.repository.unit_of_work import UnitOfWork


logger = logging.getLogger(__name__)


class PredictionService(BaseService):
    """Service for sentiment forecasting and anomaly detection.
    
    Predicts future sentiment trends using ARIMA models and identifies
    anomalous patterns in review data. Supports both single-place and
    batch forecasting operations.
    """

    # ARIMA parameter search space
    ARIMA_P_RANGE = range(0, 4)
    ARIMA_D_RANGE = range(0, 2)
    ARIMA_Q_RANGE = range(0, 4)
    
    # Anomaly detection thresholds
    SPIKE_MULTIPLIER = 2.0  # Sudden changes > 2x are spikes
    MIN_HISTORICAL_POINTS = 10  # Minimum data points for forecasting

    def __init__(self, unit_of_work: UnitOfWork) -> None:
        """Initialize PredictionService.
        
        Args:
            unit_of_work: UnitOfWork instance for repository access and
                transaction management.
        """
        super().__init__(unit_of_work)
        logger.info("PredictionService initialized")

    def forecast_sentiment(
        self,
        place_id: str,
        days_ahead: int = 30,
        confidence: float = 0.95,
    ) -> ForecastDTO:
        """Forecast sentiment for a place over specified future period.
        
        Uses ARIMA (AutoRegressive Integrated Moving Average) to forecast
        future sentiment trends. Returns predictions, confidence intervals,
        model quality metrics (RMSE, MAPE), and model type.
        
        Args:
            place_id: Unique identifier for the place to forecast.
            days_ahead: Number of days to forecast (1-365, default: 30).
            confidence: Confidence level for intervals (0.80-0.99, default: 0.95).
        
        Returns:
            ForecastDTO containing predictions, confidence intervals,
            lower/upper bounds, model type, and quality metrics (RMSE, MAPE).
        
        Raises:
            ValidationException: If parameters invalid (place_id format,
                days_ahead range, confidence level).
            ServiceException: If place doesn't exist, insufficient historical
                data, or forecasting algorithm fails.
        
        Example:
            >>> forecast = pred_service.forecast_sentiment(
            ...     place_id="place_123",
            ...     days_ahead=30,
            ...     confidence=0.95
            ... )
            >>> for date, value in forecast.predictions:
            ...     print(f"{date}: {value}")
            >>> print(f"Model quality (RMSE): {forecast.rmse}")
        """
        logger.info(
            f"Starting forecast for {place_id}: "
            f"days={days_ahead}, confidence={confidence}"
        )
        
        # Layer 1: Input Validation (before transaction)
        InputValidator.validate_place_id(place_id)
        InputValidator.validate_numeric_range(days_ahead, 1, 365)
        InputValidator.validate_numeric_range(confidence, 0.80, 0.99)
        
        # Check cache before transaction
        cache_key = self._generate_cache_key(
            "forecast", place_id, days_ahead, confidence
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
            DomainValidator.validate_sufficient_historical_data(
                place_id,
                min_reviews=10,
                min_days=60,
                unit_of_work=self.unit_of_work,
            )
            
            logger.debug(f"Domain validation passed for {place_id}")
            
            # Fetch historical sentiment time-series
            end_date = date.today()
            start_date = end_date - timedelta(days=90)  # Last 90 days
            
            try:
                reviews = self.unit_of_work.reviews.get_reviews_for_place(
                    place_id, start_date, end_date
                )
            except Exception as e:
                raise ServiceException(
                    error_code="FORECAST_DATA_FETCH_FAILED",
                    message=f"Failed to fetch forecast data for {place_id}",
                    context={
                        "place_id": place_id,
                        "error": str(e),
                    },
                )
            
            if len(reviews) < self.MIN_HISTORICAL_POINTS:
                raise ServiceException(
                    error_code="INSUFFICIENT_HISTORICAL_DATA",
                    message=(
                        f"Insufficient data for forecasting "
                        f"({len(reviews)}/{self.MIN_HISTORICAL_POINTS} reviews)"
                    ),
                    context={
                        "place_id": place_id,
                        "available_points": len(reviews),
                        "required_points": self.MIN_HISTORICAL_POINTS,
                    },
                )
            
            # Extract sentiment time-series
            time_series = self._extract_sentiment_time_series(place_id, reviews)
            
            if len(time_series) < self.MIN_HISTORICAL_POINTS:
                raise ServiceException(
                    error_code="INSUFFICIENT_TIME_SERIES",
                    message="Insufficient time-series data for forecasting",
                    context={
                        "place_id": place_id,
                        "data_points": len(time_series),
                    },
                )
            
            # Perform forecasting
            try:
                forecast_dto = self._perform_arima_forecast(
                    place_id, time_series, days_ahead, confidence
                )
            except Exception as e:
                logger.warning(
                    f"ARIMA failed for {place_id}, using fallback: {e}"
                )
                # Fallback to exponential smoothing
                forecast_dto = self._perform_exponential_smoothing_forecast(
                    place_id, time_series, days_ahead, confidence
                )
            
            logger.info(
                f"Forecast complete for {place_id}: "
                f"model={forecast_dto.model_type}, rmse={forecast_dto.rmse:.4f}"
            )
        
        # Cache result for 24 hours (86400 seconds)
        self.set_cached(cache_key, forecast_dto, ttl=86400)
        self._register_invalidation_pattern("forecast_*")
        
        return forecast_dto

    def detect_anomalies(
        self,
        place_id: str,
        sensitivity: float = 0.95,
    ) -> List[AnomalyDTO]:
        """Detect anomalous sentiment patterns in review data.
        
        Uses statistical methods (z-score and spike detection) to identify
        unusual sentiment values and sudden changes. Returns sorted by
        severity (most anomalous first).
        
        Args:
            place_id: Unique identifier for the place.
            sensitivity: Sensitivity level (0.80-0.99, default: 0.95).
                Higher values flag fewer anomalies (stricter threshold).
        
        Returns:
            List of AnomalyDTO sorted by severity (descending).
            Empty list if no anomalies detected.
        
        Raises:
            ValidationException: If place_id invalid or sensitivity invalid.
            ServiceException: If place doesn't exist or insufficient data.
        
        Example:
            >>> anomalies = pred_service.detect_anomalies(
            ...     place_id="place_123",
            ...     sensitivity=0.95
            ... )
            >>> for anomaly in anomalies:
            ...     print(f"{anomaly.timestamp}: {anomaly.description}")
            ...     print(f"Severity: {anomaly.severity}")
        """
        logger.info(f"Detecting anomalies for {place_id} (sensitivity={sensitivity})")
        
        # Layer 1: Input Validation
        InputValidator.validate_place_id(place_id)
        InputValidator.validate_numeric_range(sensitivity, 0.80, 0.99)
        
        # Check cache
        cache_key = self._generate_cache_key(
            "anomalies", place_id, sensitivity
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
            
            # Fetch historical data (last 90 days)
            end_date = date.today()
            start_date = end_date - timedelta(days=90)
            
            try:
                reviews = self.unit_of_work.reviews.get_reviews_for_place(
                    place_id, start_date, end_date
                )
            except Exception as e:
                raise ServiceException(
                    error_code="ANOMALY_DATA_FETCH_FAILED",
                    message=f"Failed to fetch data for anomaly detection",
                    context={"place_id": place_id, "error": str(e)},
                )
            
            if len(reviews) < 5:
                raise ServiceException(
                    error_code="INSUFFICIENT_DATA_FOR_ANOMALY",
                    message=f"Need at least 5 reviews for anomaly detection",
                    context={"place_id": place_id, "available": len(reviews)},
                )
            
            # Extract sentiment time-series
            time_series = self._extract_sentiment_time_series(place_id, reviews)
            
            # Detect anomalies using z-score and spike detection
            anomalies = self._detect_statistical_anomalies(
                place_id, time_series, sensitivity
            )
        
        # Cache for 3600s (1 hour)
        self.set_cached(cache_key, anomalies, ttl=3600)
        
        logger.info(f"Detected {len(anomalies)} anomalies for {place_id}")
        return anomalies

    def batch_forecast(
        self,
        place_ids: List[str],
        days_ahead: int = 30,
        max_workers: int = 5,
    ) -> Dict[str, ForecastDTO]:
        """Forecast sentiment for multiple places in parallel.
        
        Performs forecasting for a batch of places using parallel execution.
        Handles partial failures gracefully - returns forecasts for
        successful places and logs errors for failed ones.
        
        Args:
            place_ids: List of place identifiers to forecast.
            days_ahead: Number of days to forecast (default: 30).
            max_workers: Maximum parallel workers (default: 5).
        
        Returns:
            Dictionary mapping place_id to ForecastDTO for successful
            forecasts. Failed places are logged but not included.
        
        Raises:
            ValidationException: If place_ids empty or invalid.
            ServiceException: If batch forecasting fails catastrophically.
        
        Example:
            >>> forecasts = pred_service.batch_forecast(
            ...     place_ids=["place_1", "place_2", "place_3"],
            ...     days_ahead=30
            ... )
            >>> for place_id, forecast in forecasts.items():
            ...     print(f"{place_id}: {len(forecast.predictions)} predictions")
        """
        logger.info(f"Starting batch forecast for {len(place_ids)} places")
        
        # Layer 1: Input Validation
        InputValidator.validate_list_not_empty(place_ids, item_type=str)
        InputValidator.validate_numeric_range(days_ahead, 1, 365)
        
        results: Dict[str, ForecastDTO] = {}
        errors: Dict[str, str] = {}
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        self.forecast_sentiment, place_id, days_ahead
                    ): place_id
                    for place_id in place_ids
                }
                
                for future in as_completed(futures):
                    place_id = futures[future]
                    try:
                        result = future.result(timeout=300)
                        results[place_id] = result
                        logger.debug(f"✓ Forecast {place_id}")
                    except ValidationException as e:
                        errors[place_id] = f"Validation: {e.message}"
                        logger.warning(f"✗ {place_id}: {e.message}")
                    except ServiceException as e:
                        errors[place_id] = f"Service: {e.message}"
                        logger.warning(f"✗ {place_id}: {e.message}")
                    except Exception as e:
                        errors[place_id] = f"Error: {str(e)}"
                        logger.error(f"✗ {place_id}: {str(e)}")
        
        except Exception as e:
            raise ServiceException(
                error_code="BATCH_FORECAST_FAILED",
                message=f"Batch forecast failed: {str(e)}",
                context={"place_count": len(place_ids), "error": str(e)},
            )
        
        logger.info(
            f"Batch forecast complete: {len(results)} succeeded, "
            f"{len(errors)} failed"
        )
        
        return results

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _extract_sentiment_time_series(
        self,
        place_id: str,
        reviews: List[Any],
    ) -> List[Tuple[date, float]]:
        """Extract sentiment time-series from reviews.
        
        Args:
            place_id: Place identifier.
            reviews: List of review objects.
        
        Returns:
            List of (date, sentiment_score) tuples sorted by date.
        """
        time_series = []
        
        for review in reviews:
            try:
                review_date = getattr(review, "created_at", date.today())
                if isinstance(review_date, datetime):
                    review_date = review_date.date()
                
                text = getattr(review, "text", "")
                rating = getattr(review, "rating", 3.0)
                
                # Calculate sentiment (0-1, then convert to -1 to 1)
                polarity = self._calculate_polarity(text)
                rating_norm = min(rating / 5.0, 1.0)
                sentiment = ((polarity * 0.6) + (rating_norm * 0.4) * 2) - 1
                
                time_series.append((review_date, sentiment))
            except Exception as e:
                logger.warning(f"Failed to extract sentiment from review: {e}")
                continue
        
        # Sort by date
        time_series.sort(key=lambda x: x[0])
        return time_series

    def _calculate_polarity(self, text: str) -> float:
        """Calculate text polarity (-1 to 1).
        
        Args:
            text: Review text.
        
        Returns:
            Polarity score.
        """
        if not text:
            return 0.0
        
        try:
            from textblob import TextBlob
            return TextBlob(text).sentiment.polarity
        except ImportError:
            return self._fallback_polarity(text)
        except Exception as e:
            logger.warning(f"Polarity calculation error: {e}")
            return self._fallback_polarity(text)

    def _fallback_polarity(self, text: str) -> float:
        """Fallback polarity using word counting.
        
        Args:
            text: Review text.
        
        Returns:
            Polarity score.
        """
        text_lower = text.lower()
        positive = {"great", "good", "excellent", "amazing", "wonderful", "love"}
        negative = {"bad", "poor", "terrible", "awful", "hate", "horrible"}
        
        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)
        
        total = pos_count + neg_count
        return (pos_count - neg_count) / total if total > 0 else 0.0

    def _perform_arima_forecast(
        self,
        place_id: str,
        time_series: List[Tuple[date, float]],
        days_ahead: int,
        confidence: float,
    ) -> ForecastDTO:
        """Perform ARIMA-based forecasting.
        
        Args:
            place_id: Place identifier.
            time_series: Historical sentiment time-series.
            days_ahead: Days to forecast.
            confidence: Confidence level.
        
        Returns:
            ForecastDTO with predictions and metrics.
        """
        try:
            from statsmodels.tsa.arima.model import ARIMA
            
            # Extract values
            values = [s for _, s in time_series]
            dates = [d for d, _ in time_series]
            
            # Auto-select ARIMA parameters (simplified AIC-based selection)
            best_aic = float("inf")
            best_params = (1, 1, 1)
            
            for p in self.ARIMA_P_RANGE:
                for d in self.ARIMA_D_RANGE:
                    for q in self.ARIMA_Q_RANGE:
                        try:
                            model = ARIMA(values, order=(p, d, q))
                            fitted = model.fit()
                            if fitted.aic < best_aic:
                                best_aic = fitted.aic
                                best_params = (p, d, q)
                        except Exception:
                            continue
            
            # Fit final model
            model = ARIMA(values, order=best_params)
            fitted_model = model.fit()
            
            # Generate forecast
            forecast_result = fitted_model.get_forecast(steps=days_ahead)
            forecast_mean = forecast_result.predicted_mean.tolist()
            forecast_ci = forecast_result.conf_int(alpha=1 - confidence)
            
            # Build prediction tuples
            predictions = []
            lower_bounds = []
            upper_bounds = []
            
            last_date = dates[-1]
            for i, pred_value in enumerate(forecast_mean):
                pred_date = last_date + timedelta(days=i + 1)
                predictions.append((pred_date, float(pred_value)))
                lower_bounds.append(float(forecast_ci.iloc[i, 0]))
                upper_bounds.append(float(forecast_ci.iloc[i, 1]))
            
            # Calculate RMSE and MAPE
            fitted_values = fitted_model.fittedvalues.tolist()
            rmse = (
                (sum((values[i] - fitted_values[i]) ** 2 for i in range(len(values)))
                / len(values)) ** 0.5
            )
            
            mape = (
                sum(abs((values[i] - fitted_values[i]) / values[i])
                for i in range(len(values)) if values[i] != 0)
                / len(values) * 100
            )
            
            logger.debug(
                f"ARIMA forecast successful for {place_id}: "
                f"params={best_params}, rmse={rmse:.4f}"
            )
            
            return ForecastDTO(
                predictions=predictions,
                confidence_intervals=[
                    (lower_bounds[i], upper_bounds[i]) for i in range(len(predictions))
                ],
                lower_bound=lower_bounds,
                upper_bound=upper_bounds,
                model_type="ARIMA",
                rmse=rmse,
                mape=mape,
                timestamp=datetime.now(),
            )
        
        except ImportError:
            logger.warning("statsmodels not available, using fallback")
            raise
        except Exception as e:
            logger.warning(f"ARIMA forecast failed: {e}")
            raise

    def _perform_exponential_smoothing_forecast(
        self,
        place_id: str,
        time_series: List[Tuple[date, float]],
        days_ahead: int,
        confidence: float,
    ) -> ForecastDTO:
        """Fallback exponential smoothing forecast.
        
        Args:
            place_id: Place identifier.
            time_series: Historical sentiment time-series.
            days_ahead: Days to forecast.
            confidence: Confidence level.
        
        Returns:
            ForecastDTO with predictions.
        """
        values = [s for _, s in time_series]
        dates = [d for d, _ in time_series]
        
        # Simple exponential smoothing (alpha = 0.3)
        alpha = 0.3
        
        # Initialize
        smoothed = [values[0]]
        for i in range(1, len(values)):
            smoothed.append(alpha * values[i] + (1 - alpha) * smoothed[-1])
        
        # Forecast
        last_smoothed = smoothed[-1]
        predictions = []
        lower_bounds = []
        upper_bounds = []
        
        # Estimate standard error
        residuals = [values[i] - smoothed[i] for i in range(len(values))]
        std_error = (sum(r ** 2 for r in residuals) / len(residuals)) ** 0.5
        
        # Z-score for confidence level (95% ≈ 1.96)
        z_score = 1.96 if confidence >= 0.95 else 1.645
        
        last_date = dates[-1]
        for i in range(days_ahead):
            pred_date = last_date + timedelta(days=i + 1)
            pred_value = last_smoothed  # Flat forecast
            
            # Widen intervals over time
            interval_width = std_error * z_score * (1 + (i / days_ahead))
            
            predictions.append((pred_date, float(pred_value)))
            lower_bounds.append(float(pred_value - interval_width))
            upper_bounds.append(float(pred_value + interval_width))
        
        # Calculate RMSE
        rmse = std_error
        mape = (
            sum(abs(residuals[i] / values[i]) for i in range(len(values)) if values[i] != 0)
            / len(values) * 100
        )
        
        logger.info(f"Fallback forecast (exponential smoothing) for {place_id}")
        
        return ForecastDTO(
            predictions=predictions,
            confidence_intervals=[
                (lower_bounds[i], upper_bounds[i]) for i in range(len(predictions))
            ],
            lower_bound=lower_bounds,
            upper_bound=upper_bounds,
            model_type="ExponentialSmoothing",
            rmse=rmse,
            mape=mape,
            timestamp=datetime.now(),
        )

    def _detect_statistical_anomalies(
        self,
        place_id: str,
        time_series: List[Tuple[date, float]],
        sensitivity: float,
    ) -> List[AnomalyDTO]:
        """Detect anomalies using z-score and spike detection.
        
        Args:
            place_id: Place identifier.
            time_series: Historical sentiment time-series.
            sensitivity: Detection sensitivity (0.80-0.99).
        
        Returns:
            List of AnomalyDTO sorted by severity.
        """
        if len(time_series) < 3:
            return []
        
        values = [s for _, s in time_series]
        dates = [d for d, _ in time_series]
        
        # Calculate statistics
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        
        if stdev == 0:
            return []
        
        # Z-score threshold based on sensitivity
        # 0.95 sensitivity ≈ 1.96 z-score (95% confidence)
        z_threshold = 1.96 + ((1 - sensitivity) * 5)
        
        anomalies = []
        
        for i, (date_val, sentiment) in enumerate(time_series):
            z_score = (sentiment - mean) / stdev if stdev > 0 else 0
            
            # Z-score anomaly
            if abs(z_score) > z_threshold:
                severity = min(abs(z_score) / 3.0, 1.0)  # Normalize to 0-1
                anomalies.append(
                    AnomalyDTO(
                        timestamp=datetime.combine(date_val, datetime.min.time()),
                        value=sentiment,
                        z_score=z_score,
                        severity=severity,
                        description=f"Extreme sentiment score (z={z_score:.2f})",
                        suggested_action="Review content and reviewer credibility",
                    )
                )
            
            # Spike detection
            if i > 0 and i < len(values) - 1:
                prev_val = values[i - 1]
                next_val = values[i + 1]
                
                if prev_val != 0 and next_val != 0:
                    prev_ratio = abs(sentiment / prev_val)
                    next_ratio = abs(sentiment / next_val)
                    
                    if prev_ratio > self.SPIKE_MULTIPLIER or next_ratio > self.SPIKE_MULTIPLIER:
                        spike_severity = min(
                            max(prev_ratio, next_ratio) / self.SPIKE_MULTIPLIER, 1.0
                        )
                        anomalies.append(
                            AnomalyDTO(
                                timestamp=datetime.combine(date_val, datetime.min.time()),
                                value=sentiment,
                                z_score=z_score,
                                severity=spike_severity,
                                description=f"Sudden sentiment change detected",
                                suggested_action="Investigate cause of sentiment shift",
                            )
                        )
        
        # Sort by severity descending
        anomalies.sort(key=lambda x: x.severity, reverse=True)
        
        return anomalies

    def _generate_cache_key(self, *args: Any) -> str:
        """Generate deterministic cache key.
        
        Args:
            *args: Arguments to include in key.
        
        Returns:
            Cache key string.
        """
        return "_".join(str(arg) for arg in args)

    def _register_invalidation_pattern(self, pattern: str) -> None:
        """Register cache invalidation pattern.
        
        Args:
            pattern: Pattern for invalidation.
        """
        logger.debug(f"Registered invalidation pattern: {pattern}")


__all__ = ["PredictionService"]

