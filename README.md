# 🚀 Scraper Suite - Scraping + Análisis Integrado (v3.4.0)

Este proyecto es una solución completa para la extracción, almacenamiento, análisis y visualización de datos de reseñas de Google Maps. Combina la potencia de **Node.js/Puppeteer** para el scraping con **Python** para el análisis de datos avanzado (NLP, Machine Learning) y la visualización.

## 📋 Características Principales

### 🕷️ Scraping Avanzado
*   **Extracción de Metadatos:** Obtiene información detallada de negocios (nombre, dirección, teléfono, rating, etc.).
*   **Scraping de Reseñas:** Descarga masiva de reseñas de usuarios.
*   **Evasión de Bloqueos:** Utiliza `puppeteer-extra-plugin-stealth` y rotación de User-Agents.
*   **Soporte de Proxies:** Integración para rotación de IPs (compatible con Webshare u otros).

### 🧠 Análisis de Datos (Python)
*   **Pipeline ETL:** Limpieza y transformación de datos para su almacenamiento estructurado.
*   **NLP (Procesamiento de Lenguaje Natural):** Análisis de sentimiento y detección de temas en las reseñas.
*   **Machine Learning:**
    *   **Clustering:** Agrupación de negocios similares.
    *   **Predicción:** Pronóstico de ratings futuros y volumen de reseñas.
    *   **Correlación:** Análisis de factores que influyen en la calificación.
*   **Detección de Patrones:** Identificación de tendencias en el comportamiento de los usuarios.

### 📊 Visualización y Acceso
*   **API REST (FastAPI):** Endpoints para consultar análisis, predicciones y datos procesados.
*   **Dashboard Interactivo (Streamlit):** Visualización de KPIs, gráficos de tendencias y exploración de datos.
*   **Reportes Automáticos:** Generación de informes en formato DOCX.

---

## 🛠️ Tecnologías Utilizadas

### Backend & Análisis (Python 3.10+)
*   **FastAPI:** Framework para la API REST.
*   **Streamlit:** Dashboard interactivo.
*   **SQLAlchemy:** ORM para interacción con la base de datos.
*   **Pandas / NumPy:** Procesamiento y análisis de datos.
*   **Scikit-learn / NLTK:** Machine Learning y NLP.
*   **Python-docx:** Generación de reportes.

### Scraping (Node.js >= 20)
*   **Puppeteer:** Automatización de navegador para scraping.
*   **Inquirer:** Interfaz de línea de comandos interactiva.
*   **Winston:** Sistema de logging.

### Base de Datos
*   **SQLite:** Por defecto para desarrollo (`data/analytics.db`).
*   **PostgreSQL:** Soportado para producción (configurable en `.env`).

---

## 📂 Estructura del Proyecto

```
.
├── api/                    # API REST (FastAPI)
│   ├── v1/routers/         # Endpoints (NLP, predicción, clustering, etc.)
│   └── main.py             # Punto de entrada de la API
├── config/                 # Archivos de configuración y listas de proxies
├── dashboard/              # Aplicación de visualización (Streamlit)
├── database/               # Modelos ORM y repositorios
│   ├── models.py           # Definición de tablas (Places, Reviews, KPIs)
│   └── repository/         # Lógica de acceso a datos
├── modules/                # Scripts de scraping y utilidades
│   ├── mass_scraper_main.js # Scraper principal de reseñas
│   ├── scrape_metadata.js   # Scraper de metadatos
│   └── docx_generator.py    # Generador de reportes Word
├── tests/                  # Tests unitarios e integración
├── run.js                  # CLI Principal (Menú Interactivo)
├── package.json            # Dependencias de Node.js
└── requirements.txt        # Dependencias de Python
```

---

## 🚀 Instalación y Configuración

### 1. Prerrequisitos
*   Node.js (v20 o superior)
*   Python (v3.10 o superior)
*   Google Chrome instalado

### 2. Instalación de Dependencias

**Node.js (Scraper):**
```bash
npm install
```

**Python (Análisis y API):**
Se recomienda crear un entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configuración de Variables de Entorno
Crea un archivo `.env` en la raíz (o en `config/.env` según la configuración de `run.js`) basado en el ejemplo:
```bash
cp .env.example .env
```
Asegúrate de configurar `DATABASE_URL` y otras variables clave como `OPENAI_API_KEY` si planeas usar funciones de IA generativa.

---

## 🎮 Uso

El proyecto cuenta con un lanzador unificado (`run.js`) que ofrece un menú interactivo para todas las tareas.

Para iniciar el menú principal:

```bash
npm start
# o directamente
node run.js
```

### Opciones del Menú:
1.  **🔍 Metadata Scraper:** Busca y extrae información básica de locales.
2.  **⭐ Reviews Scraper:** Descarga reseñas de los locales encontrados.
3.  **🤖 Test Proxies:** Verifica la funcionalidad de tus proxies.
4.  **📊 Analytics & AI:** Accede al sub-menú de análisis Python (ETL, NLP, Predicción, etc.).
5.  **📈 Start Dashboard:** Inicia la interfaz visual de Streamlit.
6.  **🌐 Start API Server:** Levanta el servidor FastAPI.
7.  **📄 Generate Reports:** Crea documentos DOCX con los hallazgos.

---

## 🧪 Tests

Para ejecutar los tests de Python:
```bash
pytest tests/
```

## 📝 Licencia
Este proyecto está bajo la licencia MIT.
