"""
Database Models - SQLAlchemy ORM Definitions

This module defines all database tables and relationships for the analytics pipeline.
Supports both SQLite (development) and PostgreSQL (production).

Tables:
- places: Restaurant/business metadata
- reviews: Individual review records
- owner_responses: Owner responses to reviews
- kpi_summary: Aggregated KPIs by period
- analysis_cache: Performance caching layer
- nlp_analysis_results: NLP sentiment and context analysis (PHASE 2)
- predictions: Rating and volume forecasts (PHASE 2)
- correlation_analysis: Factor drivers and impact analysis (PHASE 2)
- place_clusters: K-Means clustering results (PHASE 2)
- review_patterns: Detected behavioral patterns (PHASE 2)
- analytics_runs: Pipeline execution audit trail (PHASE 2)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime,
    ForeignKey, Boolean, JSON, Index, UniqueConstraint,
    create_engine, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, Mapped
from sqlalchemy.pool import StaticPool

Base = declarative_base()


class Places(Base):
    """
    Tabla de locales/negocios.

    Almacena información general del negocio scrapeado.
    Relación 1:N con Reviews y OwnerResponses.
    """
    __tablename__ = "places"
    __table_args__ = (
        Index('idx_place_id_unique', 'place_id', unique=True),
        Index('idx_name_location', 'name', 'location'),
    )

    id = Column(String(50), primary_key=True)
    place_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    location = Column(String(500), nullable=True)
    url = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)

    # Rating agregado
    rating = Column(Float, nullable=True, default=0.0)
    total_reviews = Column(Integer, nullable=True, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_scraped = Column(DateTime, nullable=True)

    # Relaciones
    reviews: Mapped[List['Reviews']] = relationship(
        'Reviews',
        back_populates='place',
        cascade='all, delete-orphan',
        lazy='select'
    )
    kpi_summaries: Mapped[List['KPISummary']] = relationship(
        'KPISummary',
        back_populates='place',
        cascade='all, delete-orphan',
        lazy='select'
    )

    def __repr__(self) -> str:
        return f"<Place(id='{self.id}', name='{self.name}', rating={self.rating})>"

    def to_dict(self) -> dict:
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'place_id': self.place_id,
            'name': self.name,
            'location': self.location,
            'url': self.url,
            'phone': self.phone,
            'rating': self.rating,
            'total_reviews': self.total_reviews,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_scraped': self.last_scraped.isoformat() if self.last_scraped else None
        }


class Reviews(Base):
    """
    Tabla de reseñas individuales.

    Almacena cada reseña scrapeada con su metadata y análisis.
    Relación N:1 con Places.
    """
    __tablename__ = "reviews"
    __table_args__ = (
        Index('idx_review_place', 'place_id'),
        Index('idx_review_rating', 'rating'),
        Index('idx_review_date', 'review_date'),
        Index('idx_place_date', 'place_id', 'review_date'),
    )

    id = Column(String(50), primary_key=True)
    place_id = Column(String(255), ForeignKey('places.place_id', ondelete='CASCADE'), nullable=False, index=True)
    author = Column(String(255), nullable=True)
    text = Column(Text, nullable=False)
    rating = Column(Float, nullable=False)
    review_date = Column(DateTime, nullable=False)
    has_owner_response = Column(Boolean, default=False, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    place = relationship('Places', back_populates='reviews')

    def __repr__(self) -> str:
        return f"<Review(id='{self.id}', rating={self.rating}, author='{self.author}')>"

    def to_dict(self) -> dict:
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'place_id': self.place_id,
            'author': self.author,
            'text': self.text,
            'rating': self.rating,
            'review_date': self.review_date.isoformat(),
            'has_owner_response': self.has_owner_response,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class OwnerResponses(Base):
    """
    Tabla de respuestas de propietarios a reseñas.

    Almacena respuestas proporcionadas por propietarios/managers.
    Relación N:1 con Reviews.
    """
    __tablename__ = "owner_responses"
    __table_args__ = (
        Index('idx_response_review', 'review_id'),
        Index('idx_response_date', 'response_date'),
    )

    id = Column(String(50), primary_key=True)
    review_id = Column(String(50), ForeignKey('reviews.id', ondelete='CASCADE'), nullable=False, index=True)
    text = Column(Text, nullable=False)
    response_date = Column(DateTime, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<OwnerResponse(id='{self.id}', review_id='{self.review_id}')>"

    def to_dict(self) -> dict:
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'review_id': self.review_id,
            'text': self.text,
            'response_date': self.response_date.isoformat(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class KPISummary(Base):
    """
    Tabla de resumen de KPIs por período.

    Almacena métricas agregadas (rating promedio, count, etc) por período y lugar.
    Relación N:1 con Places.
    """
    __tablename__ = "kpi_summary"
    __table_args__ = (
        Index('idx_kpi_place', 'place_id'),
        Index('idx_kpi_period', 'period_start', 'period_end'),
        Index('idx_kpi_place_period', 'place_id', 'period_start'),
    )

    id = Column(String(50), primary_key=True)
    place_id = Column(String(255), ForeignKey('places.place_id', ondelete='CASCADE'), nullable=False, index=True)

    # Período
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    period_type = Column(String(50), nullable=False)  # daily, weekly, monthly

    # Métricas
    avg_rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True, default=0)
    sentiment_avg = Column(Float, nullable=True)
    response_rate = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    place = relationship('Places', back_populates='kpi_summaries')

    def __repr__(self) -> str:
        return f"<KPISummary(id='{self.id}', place_id='{self.place_id}', avg_rating={self.avg_rating})>"

    def to_dict(self) -> dict:
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'place_id': self.place_id,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'period_type': self.period_type,
            'avg_rating': self.avg_rating,
            'review_count': self.review_count,
            'sentiment_avg': self.sentiment_avg,
            'response_rate': self.response_rate,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class AnalysisCacheEntry(Base):
    """
    Tabla de caché de análisis para optimizar performance.

    Almacena resultados de análisis previamente calculados.
    Relación N:1 con Places.
    """
    __tablename__ = "analysis_cache"
    __table_args__ = (
        Index('idx_cache_place', 'place_id'),
        Index('idx_cache_type', 'analysis_type'),
        Index('idx_cache_expiry', 'expires_at'),
    )

    id = Column(String(50), primary_key=True)
    place_id = Column(String(255), ForeignKey('places.place_id', ondelete='CASCADE'), nullable=False, index=True)
    analysis_type = Column(String(100), nullable=False)
    result_data = Column(JSON, nullable=True)
    expires_at = Column(DateTime, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<AnalysisCacheEntry(id='{self.id}', type='{self.analysis_type}')>"

    def to_dict(self) -> dict:
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'place_id': self.place_id,
            'analysis_type': self.analysis_type,
            'result_data': self.result_data,
            'expires_at': self.expires_at.isoformat(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


# ============================================================================
# PHASE 2 - ADVANCED ANALYTICS MODELS
# ============================================================================

class NLPAnalysisResults(Base):
    """
    Tabla de resultados de análisis NLP avanzado.

    Almacena análisis de sentimiento, contexto y tono para cada reseña.
    Relación N:1 con Reviews.
    Permite tracking histórico de evolución de análisis.
    """
    __tablename__ = "nlp_analysis_results"
    __table_args__ = (
        Index('idx_nlp_review', 'review_id'),
                Index('idx_nlp_sentiment', 'sentiment_score'),
        Index('idx_nlp_context', 'primary_context'),
        Index('idx_nlp_language', 'language_detected'),
        Index('idx_nlp_created', 'created_at'),
    )

    id = Column(String(50), primary_key=True)
    review_id = Column(String(50), ForeignKey('reviews.id', ondelete='CASCADE'), nullable=False, index=True)

    # Detección de idioma
    language_detected = Column(String(10), nullable=False, default='es')

    # Análisis de sentimiento
    sentiment_score = Column(Float, nullable=False)
    sentiment_label = Column(String(50), nullable=True)
    sentiment_confidence = Column(Float, nullable=True)
    keywords_detected = Column(JSON, nullable=True)

    # Clasificación de contexto
    primary_context = Column(String(50), nullable=False, index=True)
    context_score = Column(Float, nullable=True)
    secondary_contexts = Column(JSON, nullable=True)
    context_reasoning = Column(Text, nullable=True)

    # Análisis de tono de respuesta
    tone_type = Column(String(50), nullable=True)
    tone_score = Column(Float, nullable=True)
    professionalism_score = Column(Float, nullable=True)
    empathy_score = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_latest = Column(Boolean, default=True, nullable=False)
    model_version = Column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<NLPAnalysisResults(review_id='{self.review_id}', sentiment={self.sentiment_score}, context='{self.primary_context}')>"

    def to_dict(self) -> dict:
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'review_id': self.review_id,
            'language_detected': self.language_detected,
            'sentiment_score': self.sentiment_score,
            'sentiment_label': self.sentiment_label,
            'sentiment_confidence': self.sentiment_confidence,
            'keywords_detected': self.keywords_detected,
            'primary_context': self.primary_context,
            'context_score': self.context_score,
            'secondary_contexts': self.secondary_contexts,
            'tone_type': self.tone_type,
            'tone_score': self.tone_score,
            'professionalism_score': self.professionalism_score,
            'empathy_score': self.empathy_score,
            'created_at': self.created_at.isoformat(),
            'is_latest': self.is_latest,
            'model_version': self.model_version
        }


class Predictions(Base):
    """
    Tabla de predicciones analíticas.

    Almacena pronósticos de rating, volumen, sentimiento, anomalías y tendencias.
    Relación N:1 con Places.
    Ventana rolling de 12 meses.
    """
    __tablename__ = "predictions"
    __table_args__ = (
        Index('idx_pred_place', 'place_id'),
        Index('idx_pred_type', 'prediction_type'),
        Index('idx_pred_date', 'valid_from', 'valid_until'),
        Index('idx_pred_place_type', 'place_id', 'prediction_type'),
    )

    id = Column(String(50), primary_key=True)
    place_id = Column(String(255), ForeignKey('places.place_id', ondelete='CASCADE'), nullable=False, index=True)

    # Tipo de predicción
    prediction_type = Column(String(50), nullable=False)

    # Fechas del pronóstico
    forecast_start_date = Column(DateTime, nullable=False)
    forecast_end_date = Column(DateTime, nullable=False)
    forecast_period_days = Column(Integer, nullable=True)

    # Pronóstico de rating
    predicted_rating = Column(Float, nullable=True)
    forecast_confidence_lower = Column(Float, nullable=True)
    forecast_confidence_upper = Column(Float, nullable=True)
    forecast_method = Column(String(50), nullable=True)

    # Pronóstico de volumen y sentimiento
    predicted_volume = Column(Integer, nullable=True)
    predicted_sentiment = Column(Float, nullable=True)

    # Detección de anomalías
    is_anomaly = Column(Boolean, default=False, nullable=False)
    anomaly_types = Column(JSON, nullable=True)
    anomaly_scores = Column(JSON, nullable=True)
    anomaly_reasoning = Column(Text, nullable=True)

    # Análisis de tendencia
    trend_direction = Column(String(20), nullable=True)
    trend_strength = Column(Float, nullable=True)
    trend_p_value = Column(Float, nullable=True)

    # Metadata y validez
    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    valid_from = Column(DateTime, nullable=False, index=True)
    valid_until = Column(DateTime, nullable=True)
    model_version = Column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<Predictions(place_id='{self.place_id}', type='{self.prediction_type}', rating={self.predicted_rating})>"

    def to_dict(self) -> dict:
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'place_id': self.place_id,
            'prediction_type': self.prediction_type,
            'forecast_start_date': self.forecast_start_date.isoformat(),
            'forecast_end_date': self.forecast_end_date.isoformat(),
            'predicted_rating': self.predicted_rating,
            'forecast_confidence_lower': self.forecast_confidence_lower,
            'forecast_confidence_upper': self.forecast_confidence_upper,
            'predicted_volume': self.predicted_volume,
            'predicted_sentiment': self.predicted_sentiment,
            'is_anomaly': self.is_anomaly,
            'anomaly_types': self.anomaly_types,
            'trend_direction': self.trend_direction,
            'trend_strength': self.trend_strength,
            'calculated_at': self.calculated_at.isoformat(),
            'valid_from': self.valid_from.isoformat(),
            'valid_until': self.valid_until.isoformat() if self.valid_until else None
        }


class CorrelationAnalysis(Base):
    """
    Tabla de análisis de correlaciones y factores.

    Almacena análisis de factores que influyen en ratings, impacto de respuestas,
    correlaciones sentimiento-respuesta e impacto de contextos.
    Relación N:1 con Places.
    """
    __tablename__ = "correlation_analysis"
    __table_args__ = (
        Index('idx_corr_place', 'place_id'),
        Index('idx_corr_type', 'analysis_type'),
        Index('idx_corr_date', 'calculated_at'),
    )

    id = Column(String(50), primary_key=True)
    place_id = Column(String(255), ForeignKey('places.place_id', ondelete='CASCADE'), nullable=False, index=True)

    # Tipo de análisis
    analysis_type = Column(String(50), nullable=False)

    # Factores principales
    ranked_factors = Column(JSON, nullable=True)

    # Impacto de respuestas del propietario
    avg_rating_with_response = Column(Float, nullable=True)
    avg_rating_without_response = Column(Float, nullable=True)
    response_impact_score = Column(Float, nullable=True)
    response_impact_details = Column(JSON, nullable=True)

    # Correlación sentimiento-respuesta
    negative_to_positive_conversion_rate = Column(Float, nullable=True)
    neutral_reviews_affected = Column(Integer, nullable=True)
    positive_reviews_affected = Column(Integer, nullable=True)
    correlation_strength = Column(Float, nullable=True)

    # Impacto basado en contexto
    top_contexts_by_impact = Column(JSON, nullable=True)

    # Estadísticas
    sample_size = Column(Integer, nullable=True)
    confidence_level = Column(Float, nullable=True, default=0.95)
    analysis_period_days = Column(Integer, nullable=True)

    # Metadata
    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    valid_from = Column(DateTime, nullable=False)
    valid_until = Column(DateTime, nullable=True)
    model_version = Column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<CorrelationAnalysis(place_id='{self.place_id}', type='{self.analysis_type}')>"

    def to_dict(self) -> dict:
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'place_id': self.place_id,
            'analysis_type': self.analysis_type,
            'ranked_factors': self.ranked_factors,
            'avg_rating_with_response': self.avg_rating_with_response,
            'avg_rating_without_response': self.avg_rating_without_response,
            'response_impact_score': self.response_impact_score,
            'negative_to_positive_conversion_rate': self.negative_to_positive_conversion_rate,
            'correlation_strength': self.correlation_strength,
            'top_contexts_by_impact': self.top_contexts_by_impact,
            'sample_size': self.sample_size,
            'confidence_level': self.confidence_level,
            'calculated_at': self.calculated_at.isoformat(),
            'valid_from': self.valid_from.isoformat(),
            'valid_until': self.valid_until.isoformat() if self.valid_until else None
        }


class PlaceClusters(Base):
    """
    Tabla de asignaciones de clusters y perfiles de lugares.

    Almacena resultados de clustering K-Means (5 perfiles de lugares),
    movimientos de cluster, y patrones de comportamiento detectados.
    Relación N:1 con Places.
    Mantiene histórico de cambios de cluster (snapshots mensuales).
    """
    __tablename__ = "place_clusters"
    __table_args__ = (
        Index('idx_cluster_place', 'place_id'),
        Index('idx_cluster_id', 'cluster_id'),
        Index('idx_cluster_label', 'cluster_label'),
        Index('idx_cluster_date', 'calculated_at'),
    )

    id = Column(String(50), primary_key=True)
    place_id = Column(String(255), ForeignKey('places.place_id', ondelete='CASCADE'), nullable=False, index=True)

    # Asignación de cluster
    cluster_id = Column(Integer, nullable=False)
    cluster_label = Column(String(50), nullable=False)
    cluster_score = Column(Float, nullable=True)

    # Perfil del cluster
    cluster_profile = Column(JSON, nullable=True)

    # Movimiento de cluster
    previous_cluster_id = Column(Integer, nullable=True)
    cluster_movement = Column(String(50), nullable=True)
    movement_score = Column(Float, nullable=True)

    # Patrones de comportamiento detectados
    detected_patterns = Column(JSON, nullable=True)

    # Metadata
    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    valid_from = Column(DateTime, nullable=False)
    clustering_period = Column(String(100), nullable=True)
    model_version = Column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<PlaceClusters(place_id='{self.place_id}', cluster='{self.cluster_label}', movement='{self.cluster_movement}')>"

    def to_dict(self) -> dict:
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'place_id': self.place_id,
            'cluster_id': self.cluster_id,
            'cluster_label': self.cluster_label,
            'cluster_score': self.cluster_score,
            'cluster_profile': self.cluster_profile,
            'previous_cluster_id': self.previous_cluster_id,
            'cluster_movement': self.cluster_movement,
            'movement_score': self.movement_score,
            'detected_patterns': self.detected_patterns,
            'calculated_at': self.calculated_at.isoformat(),
            'valid_from': self.valid_from.isoformat(),
            'clustering_period': self.clustering_period
        }


class ReviewPatterns(Base):
    """
    Tabla de patrones detectados en contenido y comportamiento de reseñas.

    Almacena patrones recurrentes (tendencias, cíclicos, estacionales, etc)
    con recomendaciones para mejorar. Relación N:1 con Places.
    Mantiene histórico para tracking de evolución de patrones.
    """
    __tablename__ = "review_patterns"
    __table_args__ = (
        Index('idx_pattern_place', 'place_id'),
        Index('idx_pattern_type', 'pattern_type'),
        Index('idx_pattern_active', 'is_active'),
    )

    id = Column(String(50), primary_key=True)
    place_id = Column(String(255), ForeignKey('places.place_id', ondelete='CASCADE'), nullable=False, index=True)

    # Tipo y descripción del patrón
    pattern_type = Column(String(50), nullable=False)
    pattern_name = Column(String(100), nullable=False)
    pattern_description = Column(Text, nullable=True)

    # Intensidad y frecuencia
    frequency = Column(Float, nullable=True)
    sentiment_correlation = Column(Float, nullable=True)
    review_count_in_pattern = Column(Integer, nullable=True)

    # Detalles del patrón
    affected_contexts = Column(JSON, nullable=True)
    affected_ratings = Column(JSON, nullable=True)
    temporal_info = Column(JSON, nullable=True)

    # Recomendaciones
    recommended_action = Column(Text, nullable=True)
    action_priority = Column(String(20), nullable=True)
    expected_impact = Column(Float, nullable=True)

    # Metadata
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    valid_from = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    persistence_weeks = Column(Integer, nullable=True)
    model_version = Column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<ReviewPatterns(place_id='{self.place_id}', type='{self.pattern_type}', active={self.is_active})>"

    def to_dict(self) -> dict:
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'place_id': self.place_id,
            'pattern_type': self.pattern_type,
            'pattern_name': self.pattern_name,
            'pattern_description': self.pattern_description,
            'frequency': self.frequency,
            'sentiment_correlation': self.sentiment_correlation,
            'review_count_in_pattern': self.review_count_in_pattern,
            'affected_contexts': self.affected_contexts,
            'affected_ratings': self.affected_ratings,
            'recommended_action': self.recommended_action,
            'action_priority': self.action_priority,
            'expected_impact': self.expected_impact,
            'detected_at': self.detected_at.isoformat(),
            'valid_from': self.valid_from.isoformat(),
            'is_active': self.is_active,
            'persistence_weeks': self.persistence_weeks
        }


class AnalyticsRuns(Base):
    """
    Tabla de historial de ejecuciones del pipeline de análisis.

    Almacena información de cada ejecución del pipeline (estado, duración,
    resultados, errores). Audit trail completo de procesamiento.
    Relación N:1 con Places (opcional - puede ser para múltiples places).
    """
    __tablename__ = "analytics_runs"
    __table_args__ = (
        Index('idx_runs_place', 'place_id'),
        Index('idx_runs_status', 'status'),
        Index('idx_runs_date', 'started_at'),
    )

    id = Column(String(50), primary_key=True)
    place_id = Column(String(255), ForeignKey('places.place_id', ondelete='CASCADE'), nullable=True, index=True)

    # Tipo y configuración de ejecución
    run_type = Column(String(50), nullable=False)

    # Información temporal
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Estado de ejecución
    status = Column(String(50), nullable=False, default='pending')

    # Resultados del procesamiento
    reviews_processed = Column(Integer, nullable=True)
    nlp_results_generated = Column(Integer, nullable=True)
    predictions_generated = Column(Integer, nullable=True)
    correlations_generated = Column(Integer, nullable=True)
    clusters_updated = Column(Boolean, nullable=True)

    # Información de errores
    error_message = Column(Text, nullable=True)
    error_type = Column(String(100), nullable=True)
    error_context = Column(JSON, nullable=True)

    # Versiones de componentes
    engine_versions = Column(JSON, nullable=True)

    # Metadata
    triggered_by = Column(String(50), nullable=True, default='manual')

    def __repr__(self) -> str:
        return f"<AnalyticsRuns(run_type='{self.run_type}', status='{self.status}', duration={self.duration_seconds}s)>"

    def to_dict(self) -> dict:
        """Convertir objeto a diccionario."""
        return {
            'id': self.id,
            'place_id': self.place_id,
            'run_type': self.run_type,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'status': self.status,
            'reviews_processed': self.reviews_processed,
            'nlp_results_generated': self.nlp_results_generated,
            'predictions_generated': self.predictions_generated,
            'clusters_updated': self.clusters_updated,
            'error_message': self.error_message,
            'error_type': self.error_type,
            'triggered_by': self.triggered_by
        }


# ============================================================================
# DATABASE MANAGEMENT HELPER FUNCTIONS
# ============================================================================

def get_database_url(env: str = 'sqlite') -> str:
    """
    Obtener URL de conexión a base de datos según ambiente.

    Args:
        env: Tipo de ambiente ('sqlite', 'postgresql')

    Returns:
        URL de conexión
    """
    import os
    from dotenv import load_dotenv

    load_dotenv()

    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url

    if env == 'sqlite':
        return 'sqlite:///./data/analytics.db'
    elif env == 'postgresql':
        return 'postgresql://user:password@localhost/analytics_db'

    return 'sqlite:///./data/analytics.db'


def create_db_engine(database_url: str = None, echo: bool = False):
    """
    Crear motor SQLAlchemy.

    Args:
        database_url: URL de conexión
        echo: Si True, mostrar SQL en logs

    Returns:
        Motor SQLAlchemy
    """
    if database_url is None:
        database_url = get_database_url()

    # Configuración específica para SQLite
    if 'sqlite' in database_url:
        engine = create_engine(
            database_url,
            echo=echo,
            connect_args={'check_same_thread': False},
            poolclass=StaticPool,
        )
    else:
        # PostgreSQL
        engine = create_engine(
            database_url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )

    return engine


def init_db(database_url: str = None) -> None:
    """
    Inicializar base de datos (crear tablas).

    Args:
        database_url: URL de conexión (opcional)
    """
    if database_url is None:
        database_url = get_database_url()

    engine = create_db_engine(database_url)
    Base.metadata.create_all(engine)
    print(f"✅ Database initialized at: {database_url}")


def drop_db(database_url: str = None) -> None:
    """
    Eliminar todas las tablas (para testing).

    Args:
        database_url: URL de conexión (opcional)
    """
    if database_url is None:
        database_url = get_database_url()

    engine = create_db_engine(database_url)
    Base.metadata.drop_all(engine)
    print(f"✅ Database dropped")

