#!/usr/bin/env python3
import sys
import os
from pathlib import Path
from datetime import datetime
import subprocess
import re

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "analisis"))

import pandas as pd
import logging

try:
    from docx import Document
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from openai import OpenAI

def get_csv_path() -> str:
    while True:
        path = input("\nIngresa la ruta del archivo CSV: ").strip('"')
        path = Path(path)
        if not path.exists():
            logger.error(f"Archivo no encontrado: {path}")
            continue
        if not path.suffix.lower() == '.csv':
            logger.error("Debes ingresar un archivo .csv")
            continue
        return str(path)

def read_csv(csv_path: str) -> tuple:
    try:
        df = pd.read_csv(csv_path, encoding='utf-8')
    except (UnicodeDecodeError, UnicodeError):
        df = pd.read_csv(csv_path, encoding='latin-1')
    if 'rating' not in df.columns or 'text' not in df.columns:
        logger.error("❌ CSV debe tener columnas 'rating' y 'text'")
        sys.exit(1)
    reviews_text = ""
    for idx, row in df.iterrows():
        rating = row.get('rating', '?')
        text = row.get('text', '')
        author = row.get('author', 'Usuario')
        date = row.get('date', '')
        if pd.isna(text) or text == '':
            continue
        reviews_text += f"[{rating}⭐] {author} ({date}):\n{text}\n\n"
    return reviews_text, df, csv_path

def load_prompt() -> str:
    prompt_paths = [
        Path(__file__).parent.parent / "config" / "prompt.txt",
        Path(__file__).parent.parent / "analisis" / "prompt.txt",
    ]
    for p in prompt_paths:
        if p.exists():
            return p.read_text(encoding='utf-8')
    logger.warning("⚠️  prompt.txt no encontrado, usando prompt por defecto...")
    return """Eres un consultor senior en Marketing Digital especializado en Reputación Online (ORM).
Recibirás reseñas de Google Maps de un negocio específico.
Analiza TODAS las reseñas proporcionadas sin límite.
Genera un informe estratégico, profesional y orientado a acción en español.
Máximo 3600 palabras.

=== RESEÑAS ===
{{reviews_text}}

Proporciona:
1. Resumen ejecutivo
2. Análisis de sentimiento
3. KPIs principales
4. Patrones identificados
5. Recomendaciones accionables"""

def analyze_with_ai(reviews_text: str, prompt_template: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ Variable OPENAI_API_KEY no configurada")
        sys.exit(1)
    client = OpenAI(api_key=api_key)
    full_prompt = prompt_template.replace("{{reviews_text}}", reviews_text)
    logger.info("🤖 Enviando a OpenAI para análisis...")
    
    logging.getLogger("openai").setLevel(logging.ERROR)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": full_prompt}],
        temperature=0.3,
    )
    
    logging.getLogger("openai").setLevel(logging.INFO)
    
    return response.choices[0].message.content



def clean_markdown_tables(text: str) -> str:
    """Preserve Markdown tables, remove only empty/decorative lines"""
    lines = text.split('\n')
    result = []
    
    for line in lines:
        if re.match(r'^\s*$', line):
            continue
        if re.match(r'^\s*[-]{3,}\s*$', line):
            continue
        result.append(line)
    
    return '\n'.join(result)


def shade_table_headers(docx_path: str) -> None:
    """Apply gray background (#f2f2f2) to table header rows in DOCX"""
    if not DOCX_AVAILABLE:
        logger.warning("⚠️  python-docx no disponible, saltando sombreado de encabezados")
        return
    
    try:
        doc = Document(docx_path)
        headers_shaded = 0
        
        for table in doc.tables:
            if len(table.rows) == 0:
                continue
                
            for cell in table.rows[0].cells:
                shading_elm = parse_xml(
                    r'<w:shd {} w:fill="f2f2f2"/>'.format(nsdecls('w'))
                )
                cell._element.get_or_add_tcPr().append(shading_elm)
                headers_shaded += 1
        
        doc.save(docx_path)
        if headers_shaded > 0:
            logger.info(f"✨ Sombreado aplicado: {headers_shaded} celdas de encabezado")
    except Exception as e:
        logger.warning(f"⚠️  No se pudo aplicar sombreado: {e}")


def generate_docx(analysis: str, csv_path: str, reviews_count: int) -> str:
    """Generate professional DOCX report using Pandoc with reference template"""
    try:
        csv_name = Path(csv_path).stem
        output_dir = Path(csv_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{csv_name}_Informe_ORM_{timestamp}.docx"
        output_path = (output_dir / filename).resolve()
        
        generation_date = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        clean_analysis = clean_markdown_tables(analysis)
        
        markdown_content = f"""# INFORME ORM: {csv_name.upper()}

| Parámetro | Valor |
|-----------|-------|
| Fecha de Generación | {generation_date} |
| Reseñas Analizadas | {reviews_count} |

## ANÁLISIS Y HALLAZGOS

{clean_analysis}

## INFORMACIÓN DEL DOCUMENTO

| Concepto | Descripción |
|----------|-------------|
| Tipo de Análisis | Análisis de Reseñas con IA (ORM) |

---

*Análisis generado automáticamente por Quick Analysis ORM*
"""
        
        template_path = Path(__file__).parent.parent / "templates" / "orm_profesional_base_final.docx"
        
        if not template_path.exists():
            logger.warning(f"⚠️  Plantilla no encontrada en {template_path}, generando sin referencia...")
            template_arg = []
        else:
            template_arg = [f"--reference-doc={template_path}"]
        
        logger.info(f"Generando DOCX en: {output_path}")
        
        pandoc_cmd = [
            "pandoc",
            "-f", "gfm",
            "-t", "docx",
            "--variable=mainfont:Arial",
            "--variable=fontsize:12pt",
            "--variable=geometry:top=2.5cm,bottom=2.5cm,left=2.5cm,right=2.5cm",
        ] + template_arg + [
            "-o", str(output_path)
        ]
        
        process = subprocess.Popen(
            pandoc_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=markdown_content.encode('utf-8'))
        
        if process.returncode != 0:
            logger.error(f"Error ejecutando Pandoc: {stderr.decode('utf-8')}")
            raise Exception(f"Pandoc error: {stderr.decode('utf-8')}")
        
        if output_path.exists() and output_path.stat().st_size > 1000:
            shade_table_headers(str(output_path))
            file_size = output_path.stat().st_size
            logger.info(f"✅ DOCX guardado con formato profesional: {output_path} ({file_size} bytes)")
            return str(output_path)
        else:
            raise Exception(f"Archivo no creado correctamente: {output_path}")

    except FileNotFoundError:
        logger.error("❌ Pandoc no está instalado. Instálalo con: pip install pandoc")
        raise
    except Exception as e:
        logger.error(f"Error generando DOCX: {e}")
        raise



def main():
    logger.info("""
╔════════════════════════════════════════════════════════════════╗
║         QUICK ANALYSIS - Analisis Simple de CSV               ║
║                                                                ║
║  1. Solicita ruta del CSV                                      ║
║  2. Lee y valida columnas (rating, text)                       ║
║  3. Envia a OpenAI con prompt ORM                              ║
║  4. Genera DOCX profesional con analisis                       ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
    """)
    try:
        csv_path = get_csv_path()
        logger.info(f"Leyendo CSV: {csv_path}")
        reviews_text, df, _ = read_csv(csv_path)
        reviews_count = len(df)
        logger.info(f"{reviews_count} resenas cargadas")
        prompt = load_prompt()
        logger.info("Prompt cargado")
        analysis = analyze_with_ai(reviews_text, prompt)
        logger.info("Analisis completado")
        output_path = generate_docx(analysis, csv_path, reviews_count)
        logger.info(f"\nAnalisis completado!\n   Archivo: {output_path}")
    except KeyboardInterrupt:
        logger.info("\nProceso cancelado")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
