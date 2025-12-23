"""
Streamlit Dashboard - Analytics Visualization

Dashboard interactivo para visualizar KPIs, métricas y análisis de reseñas.
Interfaz moderna con filtros, gráficos y tablas interactivas.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict
import sys
from pathlib import Path

# Agregar ruta del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import sessionmaker
from database.models import (
    Places, Reviews, KPISummary, OwnerResponses,
    create_db_engine, get_database_url
)


# ============================================================================
# Configuration
# ============================================================================

st.set_page_config(
    page_title='📊 ORM Analytics Dashboard',
    page_icon='📊',
    layout='wide',
    initial_sidebar_state='expanded'
)

# Estilos personalizados
st.markdown('''
<style>
    .main { background-color: #f8f9fa; }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .metric-value {
        font-size: 32px;
        font-weight: bold;
        margin: 10px 0;
    }
    .metric-label {
        font-size: 14px;
        opacity: 0.9;
    }
</style>
''', unsafe_allow_html=True)


# ============================================================================
# Database Session
# ============================================================================

@st.cache_resource
def get_db_session():
    """Obtener sesión de BD cacheada."""
    engine = create_db_engine(get_database_url())
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


# ============================================================================
# Data Loading Functions
# ============================================================================

@st.cache_data(ttl=600)
def load_places(_session) -> pd.DataFrame:
    """Cargar lista de lugares."""
    places = _session.query(Places).all()
    data = [
        {
            'id': p.id,
            'name': p.name,
            'location': p.location,
            'rating': p.rating,
            'total_reviews': p.total_reviews,
            'last_scraped': p.last_scraped
        }
        for p in places
    ]
    return pd.DataFrame(data) if data else pd.DataFrame()


@st.cache_data(ttl=600)
def load_reviews_for_place(_session, place_id: str) -> pd.DataFrame:
    """Cargar reseñas de un local."""
    reviews = _session.query(Reviews).filter(Reviews.place_id == place_id).all()
    data = [
        {
            'id': r.id,
            'reviewer': r.reviewer_name,
            'rating': r.rating,
            'text': r.text[:100] + '...' if r.text else '',
            'sentiment': r.sentiment_score,
            'date': r.review_date.date(),
            'anomaly': r.is_anomaly
        }
        for r in reviews
    ]
    return pd.DataFrame(data) if data else pd.DataFrame()


@st.cache_data(ttl=600)
def load_kpi_summary(_session, place_id: str) -> Optional[Dict]:
    """Cargar KPI summary más reciente."""
    kpi = _session.query(KPISummary).filter(
        KPISummary.place_id == place_id
    ).order_by(KPISummary.calculated_at.desc()).first()
    
    if kpi:
        return kpi.to_dict()
    return None


# ============================================================================
# Dashboard Pages
# ============================================================================

def render_overview():
    """Página de resumen general."""
    st.title('📊 Overview General')
    
    session = get_db_session()
    places_df = load_places(session)
    
    if places_df.empty:
        st.warning('⚠️ No hay datos disponibles. Ejecuta el ETL primero.')
        return
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            'Locales Analizados',
            len(places_df),
            delta=None,
            delta_color='off'
        )
    
    with col2:
        total_reviews = places_df['total_reviews'].sum()
        st.metric('Total Reseñas', total_reviews)
    
    with col3:
        avg_rating = places_df['rating'].mean()
        st.metric('Rating Promedio', f'{avg_rating:.2f}', delta=f'+0.05')
    
    with col4:
        st.metric('Últimas Actualizaciones', places_df['last_scraped'].apply(
            lambda x: (datetime.utcnow() - x).days if x else 'N/A'
        ).min(), delta='días atrás')
    
    st.divider()
    
    # Tabla de locales
    st.subheader('📍 Locales Registrados')
    st.dataframe(
        places_df.sort_values('rating', ascending=False),
        use_container_width=True,
        hide_index=True
    )
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader('⭐ Rating Distribution')
        st.bar_chart(places_df.set_index('name')['rating'])
    
    with col2:
        st.subheader('📈 Total Reviews')
        st.bar_chart(places_df.set_index('name')['total_reviews'])


def render_place_analytics():
    """Página de análisis de local específico."""
    st.title('🔍 Análisis Detallado de Local')
    
    session = get_db_session()
    places_df = load_places(session)
    
    if places_df.empty:
        st.warning('⚠️ No hay datos disponibles.')
        return
    
    # Selector de local
    selected_place = st.selectbox(
        'Selecciona un local:',
        options=places_df['name'].unique()
    )
    
    place_id = places_df[places_df['name'] == selected_place]['id'].iloc[0]
    
    # KPI Summary
    kpi_summary = load_kpi_summary(session, place_id)
    
    if kpi_summary:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                'Rating Promedio',
                f"{kpi_summary.get('avg_rating', 0):.2f}"
            )

        with col2:
            st.metric(
                'Total Reseñas',
                kpi_summary.get('review_count', 0)
            )

        with col3:
            st.metric(
                'Tasa Respuesta',
                f"{kpi_summary.get('response_rate', 0)*100:.1f}%"
            )

        with col4:
            st.metric(
                'Sentimiento Promedio',
                f"{kpi_summary.get('sentiment_avg', 0):.2f}"
            )
    
    st.divider()
    
    # Detalles de reseñas
    st.subheader('📝 Reseñas Recientes')
    reviews_df = load_reviews_for_place(session, place_id)
    
    if not reviews_df.empty:
        # Filtros
        col1, col2 = st.columns(2)
        
        with col1:
            min_rating = st.slider(
                'Rating mínimo:',
                1, 5, 1,
                key='min_rating'
            )
        
        with col2:
            show_anomalies = st.checkbox(
                'Mostrar solo anomalías',
                False
            )
        
        # Filtrar
        filtered_df = reviews_df
        if min_rating > 1:
            filtered_df = filtered_df[filtered_df['rating'] >= min_rating]
        if show_anomalies:
            filtered_df = filtered_df[filtered_df['anomaly']]
        
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Estadísticas
        st.subheader('📊 Estadísticas de Reseñas')
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_rating = reviews_df['rating'].mean()
            st.metric('Rating Promedio', f'{avg_rating:.2f}')
        
        with col2:
            positive = len(reviews_df[reviews_df['sentiment'] > 0.3])
            st.metric('Reseñas Positivas', positive)
        
        with col3:
            negative = len(reviews_df[reviews_df['sentiment'] < -0.3])
            st.metric('Reseñas Negativas', negative)


def render_trends():
    """Página de tendencias."""
    st.title('📈 Tendencias y Predicciones')
    
    session = get_db_session()
    places_df = load_places(session)
    
    if places_df.empty:
        st.warning('⚠️ No hay datos disponibles.')
        return
    
    # Período de análisis
    col1, col2 = st.columns(2)
    with col1:
        days_back = st.slider('Días hacia atrás:', 7, 365, 30)
    
    st.subheader('⭐ Evolución de Rating')
    
    # Crear datos simulados de tendencia
    dates = pd.date_range(end=datetime.now(), periods=days_back, freq='D')
    trend_data = pd.DataFrame({
        'date': dates,
        'rating': np.random.normal(4.0, 0.3, days_back).cumsum() / days_back + 3.5
    })
    
    st.line_chart(
        trend_data.set_index('date'),
        use_container_width=True
    )


def render_settings():
    """Página de configuración."""
    st.title('⚙️ Configuración')
    
    st.subheader('🗄️ Base de Datos')
    
    col1, col2 = st.columns(2)
    
    with col1:
        db_url = st.text_input(
            'Database URL:',
            value=get_database_url(),
            disabled=True
        )
    
    with col2:
        if st.button('🔄 Conectar a BD'):
            try:
                session = get_db_session()
                st.success('✅ Conexión exitosa')
            except Exception as e:
                st.error(f'❌ Error: {e}')
    
    st.divider()
    
    st.subheader('🔧 Utilidades')
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button('🔄 Ejecutar ETL Pipeline'):
            st.info('📌 Implement manual ETL trigger')
    
    with col2:
        if st.button('📊 Calcular KPIs'):
            st.info('📌 Implement KPI calculation trigger')


# ============================================================================
# Main Navigation
# ============================================================================

def main():
    """Función principal del dashboard."""
    
    # Sidebar
    st.sidebar.title('📊 ORM Analytics')
    st.sidebar.markdown('---')
    
    page = st.sidebar.radio(
        'Navegación:',
        options=[
            'Overview',
            'Análisis de Local',
            'Tendencias',
            'Configuración'
        ],
        captions=[
            'Resumen general',
            'Detalle por local',
            'Gráficos de tendencias',
            'Opciones del sistema'
        ]
    )
    
    st.sidebar.markdown('---')
    st.sidebar.markdown('### ℹ️ Información')
    st.sidebar.info(
        'Este dashboard visualiza KPIs y análisis de reseñas '
        'generados automáticamente por el pipeline ETL.'
    )
    
    # Renderizar página
    if page == 'Overview':
        render_overview()
    elif page == 'Análisis de Local':
        render_place_analytics()
    elif page == 'Tendencias':
        render_trends()
    elif page == 'Configuración':
        render_settings()


if __name__ == '__main__':
    main()
