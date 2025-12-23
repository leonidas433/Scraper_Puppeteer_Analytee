"""
Main Orchestrator - Sistema Integral de Análisis

Orquestador central que integra:
- Inicialización de BD
- Pipeline ETL
- Motor de KPIs
- Exposición de APIs
- Dashboard

Uso:
    python main.py --init-db          # Inicializar BD
    python main.py --etl              # Ejecutar ETL
    python main.py --kpis             # Calcular KPIs
    python main.py --dashboard        # Iniciar dashboard
    python main.py --all              # Ejecutar todo
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging con soporte UTF-8
from logging_config import setup_utf8_logging, get_logger
setup_utf8_logging()
logger = get_logger(__name__)

# Importar módulos
from database.models import (
    get_database_url,
    init_db,
    drop_db
)
from analytics.data_processor import ETLPipeline
from analytics.kpi_engine import KPIEngine


# ============================================================================
# Constants
# ============================================================================

SCRAPER_DATA_PATH = os.getenv('SCRAPER_DATA_PATH', './data')
ANALYTICS_OUTPUT_PATH = os.getenv('ANALYTICS_OUTPUT_PATH', './reports')
DATABASE_URL = os.getenv('DATABASE_URL', get_database_url())


# ============================================================================
# Helper Functions
# ============================================================================

def ensure_directories():
    """Asegurar que existen directorios necesarios."""
    dirs = ['logs', 'reports', ANALYTICS_OUTPUT_PATH]
    for dir_path in dirs:
        Path(dir_path).mkdir(exist_ok=True, parents=True)
        logger.info(f'✅ Directory ready: {dir_path}')


def print_banner(title: str):
    """Imprimir banner."""
    print('\n' + '=' * 80)
    print(f'  🚀 {title}')
    print('=' * 80 + '\n')


# ============================================================================
# Orchestration Functions
# ============================================================================

def init_database():
    """Inicializar base de datos."""
    print_banner('DATABASE INITIALIZATION')
    
    try:
        logger.info(f'Initializing database: {DATABASE_URL}')
        init_db(DATABASE_URL)
        logger.info('✅ Database initialized successfully')
        return True
    except Exception as e:
        logger.error(f'❌ Database initialization failed: {e}')
        return False


def reset_database():
    """Resetear base de datos (eliminar y recrear)."""
    print_banner('DATABASE RESET')
    
    try:
        logger.warning('Dropping all tables...')
        drop_db(DATABASE_URL)
        
        logger.info('Recreating database...')
        init_db(DATABASE_URL)
        
        logger.info('✅ Database reset successfully')
        return True
    except Exception as e:
        logger.error(f'❌ Database reset failed: {e}')
        return False


def run_etl_pipeline():
    """Ejecutar pipeline ETL."""
    print_banner('ETL PIPELINE EXECUTION')
    
    try:
        pipeline = ETLPipeline(
            database_url=DATABASE_URL,
            data_path=SCRAPER_DATA_PATH
        )
        
        result = pipeline.run(full_scan=True)
        
        logger.info(f'✅ ETL completed:')
        logger.info(f"   Places: {result['places_loaded']}")
        logger.info(f"   Reviews: {result['reviews_loaded']}")
        logger.info(f"   Responses: {result['responses_loaded']}")
        logger.info(f"   Duration: {result['duration_seconds']:.2f}s")
        
        # Guardar resultado
        import json
        output_file = os.path.join(ANALYTICS_OUTPUT_PATH, 'etl_summary.json')
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f'📊 Summary saved to {output_file}')
        
        return result['status'] == 'SUCCESS'
    
    except Exception as e:
        logger.error(f'❌ ETL pipeline failed: {e}')
        return False


def run_kpi_engine():
    """Ejecutar motor de KPIs."""
    print_banner('KPI ENGINE EXECUTION')
    
    try:
        engine = KPIEngine(database_url=DATABASE_URL)
        
        period_days = int(os.getenv('DEFAULT_ANALYSIS_PERIOD_DAYS', 30))
        result = engine.calculate_all_places(period_days=period_days)
        
        logger.info(f'✅ KPI Engine completed:')
        logger.info(f"   Places: {result['places_processed']}")
        logger.info(f"   KPIs: {result['kpis_calculated']}")
        logger.info(f"   Duration: {result['duration_seconds']:.2f}s")
        
        # Exportar KPIs
        engine.export_kpis()
        
        logger.info('📊 KPIs exported to reports/kpis.json')
        
        return result['status'] == 'SUCCESS'
    
    except Exception as e:
        logger.error(f'❌ KPI Engine failed: {e}')
        return False


def run_dashboard():
    """Iniciar dashboard Streamlit."""
    print_banner('STREAMLIT DASHBOARD')
    
    try:
        import subprocess
        dashboard_path = os.path.join('dashboard', 'app.py')
        
        logger.info(f'Starting Streamlit dashboard...')
        subprocess.run(
            ['streamlit', 'run', dashboard_path],
            cwd=Path(__file__).parent
        )
        
        return True
    
    except Exception as e:
        logger.error(f'❌ Dashboard startup failed: {e}')
        logger.info('Make sure Streamlit is installed: pip install streamlit')
        return False


def run_api_server():
    """Iniciar servidor FastAPI (placeholder)."""
    print_banner('FASTAPI SERVER')
    
    logger.info('FastAPI server not yet implemented')
    logger.info('Future integration: python main.py --api')
    
    return False


def run_full_pipeline():
    """Ejecutar pipeline completo."""
    print_banner('FULL PIPELINE EXECUTION')
    
    results = {
        'database_init': False,
        'etl': False,
        'kpi_engine': False
    }
    
    logger.info('Step 1/3: Initialize Database')
    results['database_init'] = init_database()
    
    if not results['database_init']:
        logger.error('❌ Database initialization failed, stopping pipeline')
        return results
    
    logger.info('\nStep 2/3: Run ETL Pipeline')
    results['etl'] = run_etl_pipeline()
    
    if not results['etl']:
        logger.error('❌ ETL pipeline failed, skipping KPI engine')
        return results
    
    logger.info('\nStep 3/3: Run KPI Engine')
    results['kpi_engine'] = run_kpi_engine()
    
    print_banner('PIPELINE COMPLETED')
    print(f"✅ Database Init: {results['database_init']}")
    print(f"✅ ETL Pipeline: {results['etl']}")
    print(f"✅ KPI Engine: {results['kpi_engine']}")
    print('\n📊 Dashboard: streamlit run dashboard/app.py')
    print('=' * 80 + '\n')
    
    return results


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Punto de entrada principal."""
    
    parser = argparse.ArgumentParser(
        description='ORM Analytics System - Main Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python main.py --init-db              Initialize database
  python main.py --etl                  Run ETL pipeline
  python main.py --kpis                 Calculate KPIs
  python main.py --all                  Run all (DB + ETL + KPIs)
  python main.py --dashboard            Start Streamlit dashboard
  python main.py --reset-db             Reset database (WARNING: deletes data)
        '''
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--init-db', action='store_true', help='Initialize database')
    group.add_argument('--etl', action='store_true', help='Run ETL pipeline')
    group.add_argument('--kpis', action='store_true', help='Calculate KPIs')
    group.add_argument('--dashboard', action='store_true', help='Start Streamlit dashboard')
    group.add_argument('--api', action='store_true', help='Start FastAPI server')
    group.add_argument('--all', action='store_true', help='Run full pipeline')
    group.add_argument('--reset-db', action='store_true', help='Reset database (WARNING)')
    
    args = parser.parse_args()
    
    # Preparar directorios
    ensure_directories()
    
    logger.info(f'🚀 ORM Analytics System - {datetime.now().isoformat()}')
    logger.info(f'📁 Data Path: {SCRAPER_DATA_PATH}')
    logger.info(f'📊 Output Path: {ANALYTICS_OUTPUT_PATH}')
    logger.info(f'🗄️  Database URL: {DATABASE_URL}')
    
    # Ejecutar según argumentos
    if args.init_db:
        init_database()
    elif args.etl:
        run_etl_pipeline()
    elif args.kpis:
        run_kpi_engine()
    elif args.dashboard:
        run_dashboard()
    elif args.api:
        run_api_server()
    elif args.all:
        run_full_pipeline()
    elif args.reset_db:
        confirm = input('⚠️  This will DELETE all data. Continue? (yes/no): ')
        if confirm.lower() == 'yes':
            reset_database()
        else:
            logger.info('Cancelled.')
    else:
        # No arguments provided
        parser.print_help()
        print_banner('DEFAULT FULL PIPELINE')
        run_full_pipeline()


if __name__ == '__main__':
    main()
