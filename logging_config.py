"""
Logging Configuration with UTF-8 Support for Windows
=====================================================
Centraliza la configuración de logging para todos los módulos
"""

import sys
import logging
from pathlib import Path


def setup_utf8_logging():
    """
    Configurar logging con soporte UTF-8 en Windows.
    Ejecutar una sola vez al inicio de la aplicación.
    """
    # Crear directorio de logs
    Path('logs').mkdir(exist_ok=True, parents=True)
    
    # Forzar UTF-8 en consola (Windows)
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
        try:
            sys.stderr.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    
    # Obtener logger raíz
    root_logger = logging.getLogger()
    
    # Limpiar handlers existentes
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Crear formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # FileHandler con UTF-8
    file_handler = logging.FileHandler('logs/combined.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # StreamHandler con UTF-8
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)
    
    # Configurar logger raíz
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    root_logger.setLevel(logging.DEBUG)


def get_logger(name: str) -> logging.Logger:
    """
    Obtener logger configurado correctamente.
    
    Args:
        name: Nombre del módulo
        
    Returns:
        Logger configurado
    """
    return logging.getLogger(name)