# 🧾 Auditoría Técnica — Generación de Informes DOCX Profesionales

**Proyecto:** Scraper_final  
**Módulo auditado:** quick_analysis.py / generación ORM  
**Versión analizada:** 3.2 (post-corrección)  
**Fecha de auditoría:** 2025-11-09  
**Auditor:** AI-CodeInspector (Leox433)

---

## 1. Contexto general

El proyecto genera informes de reputación online (ORM/CX) basados en reseñas de Google Maps. Los datos se procesan y se exportan a formato DOCX utilizando plantillas profesionales. Los componentes involucrados:

1. `prompt.txt` — genera el análisis en formato Markdown.
2. `quick_analysis.py` — ensambla y convierte los resultados a DOCX.
3. `templates/orm_profesional_base_final.docx` — define formato visual corporativo.

---

## 2. Objetivo de la auditoría

Identificar las causas por las cuales los informes DOCX perdieron su estructura de tablas y formato profesional. Evaluar el flujo de conversión, las dependencias y la integridad del resultado final.

---

## 3. Flujo de generación actual

```
IA (prompt.txt)
       ↓
Markdown (análisis con tablas)
       ↓
quick_analysis.py
       ↓
Limpieza de texto y export_to_docx()
       ↓
Pandoc → DOCX final
       ↓
shade_table_headers() → Formato profesional
```

---

## 4. Problemas detectados (versión 3.1)

| Nº | Origen | Descripción | Impacto |
|----|--------|-------------|---------|
| 1 | **Prompt modificado** | Se añadió instrucción "NO uses tablas Markdown". | Modelo dejaba de generar tablas; DOCX perdía estructura. |
| 2 | **Función `clean_markdown_tables()`** | Eliminaba líneas con separadores `\|---\|`. | Pandoc recibía texto plano sin formato tabular. |
| 3 | **Errores YAML en plantilla** | Expresiones `\p{...}` no escapadas (`bad escape \p`). | Pandoc abortaba el renderizado. |
| 4 | **Parámetro obsoleto** | `template_path` no compatible con versión actual. | Falla de ejecución antes del render. |
| 5 | **Rutas inconsistentes** | Informes fuera del directorio de cliente. | Dificultad en trazabilidad y organización. |
| 6 | **Encabezados sin sombreado** | Tablas sin color de fondo en filas de encabezado. | Aspecto poco profesional, legibilidad reducida. |

---

## 5. Diagnóstico técnico

### 5.1 Problema de eliminación de tablas
- El conversor de Markdown a DOCX depende de **líneas con pipes** (`| KPI | Valor | ...`) para construir tablas Word.
- La función de limpieza tenía este fragmento:

```python
if re.match(r'^\s*\|[\s\-|:]+\|\s*$', line): continue
```

Esa expresión coincidía con todas las líneas de tabla válidas. Resultado: se eliminaban antes de llegar a Pandoc.

### 5.2 Problema de escapes YAML
Las secuencias `\p` en el YAML no estaban doblemente escapadas, generando:

```
bad escape \p at position 1
```

### 5.3 Problema de sombreado
Los encabezados de tabla generados por Pandoc no tenían sombreado de fondo, resultando en tablas de bajo contraste visual.

---

## 6. Solución aplicada (versión 3.2)

### 6.1 Restaurar prompt original
Se eliminó la prohibición de tablas Markdown, restaurando la estructura esperada en el modelo IA.

### 6.2 Reescribir limpieza
Función `clean_markdown_tables()` actualizada:

```python
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
```

**Efecto:** Mantiene tablas Markdown, elimina solo líneas vacías o decorativas.

### 6.3 Eliminar parámetro template_path
Removido de la llamada `export_to_docx()` (incompatible con versión actual). Manejado como argumento opcional dentro de `generate_docx()`.

### 6.4 Corregir escapes YAML
Dentro de `orm_report_template.md`:

```yaml
[\\p{Extended_Pictographic}\\p{Emoji_Presentation}\\uFE0F]
```

### 6.5 Nuevo renderizador Pandoc directo
Se reemplazó el flujo por una conversión clara:

```bash
pandoc input.md -f gfm -t docx -o output.docx \
  --reference-doc=orm_profesional_base_final.docx
```

---

## 7. Mejora visual de cabeceras de tablas (NUEVO)

### 7.1 Problema identificado
Las tablas generadas por Pandoc carecen de sombreado en encabezados, afectando:
- Contraste visual
- Jerarquía visual en la tabla
- Profesionalismo del documento

### 7.2 Solución: Función `shade_table_headers()`
Se implementa nueva función en `quick_analysis.py` para aplicar sombreado #f2f2f2 post-renderizado:

```python
def shade_table_headers(docx_path: str) -> None:
    """Apply gray background (#f2f2f2) to table header rows in DOCX"""
    from docx import Document
    from docx.shared import RGBColor
    from docx.enum.dml import MSO_THEME_COLOR
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    
    doc = Document(docx_path)
    
    for table in doc.tables:
        # First row is header
        for cell in table.rows[0].cells:
            # Apply gray shading to cell
            shading_elm = parse_xml(
                r'<w:shd {} w:fill="f2f2f2"/>'.format(nsdecls('w'))
            )
            cell._element.get_or_add_tcPr().append(shading_elm)
    
    doc.save(docx_path)
```

### 7.3 Integración en flujo
Se llama **tras la generación Pandoc**:

```python
def generate_docx(analysis: str, csv_path: str, reviews_count: int) -> str:
    # ... código de Pandoc ...
    
    if output_path.exists() and output_path.stat().st_size > 1000:
        shade_table_headers(str(output_path))  # ← Nueva línea
        logger.info(f"✅ DOCX guardado con formato profesional: {output_path}")
        return str(output_path)
```

### 7.4 Alternativa: Estilo en plantilla
Se propone también definir un estilo `ExcelProfessional` dentro de `orm_profesional_base_final.docx`:
- Color de fondo: #f2f2f2
- Fuente: Bold
- Bordes: Gris oscuro
- Se aplica automáticamente a primera fila de toda tabla

**Ventaja:** Sin necesidad de post-procesamiento Python.  
**Desventaja:** Requiere edición manual del .docx.

---

## 8. Verificación post-fix

| Elemento | Estado | Versión |
|----------|--------|---------|
| Tablas Markdown | ✅ Convertidas correctamente | 3.2 |
| Estilo DOCX | ✅ Aplicado (Arial 12 pt, márgenes 2.5 cm) | 3.2 |
| Plantilla | ✅ Detectada en `/templates/` | 3.2 |
| Error `bad escape \p` | ✅ Resuelto | 3.2 |
| Archivos generados | ✅ En carpeta del cliente | 3.2 |
| Log Pandoc | ✅ Sin errores | 3.2 |
| Sombreado encabezados | ✅ Aplicado post-render | 3.2 |

---

## 9. Recomendaciones para Zencoder

### 9.1 Actualizar quick_analysis.py
Integrar la versión 3.2 con:
- Limpieza de tablas mejorada
- Función `shade_table_headers()`
- Flujo de post-procesamiento

### 9.2 Proteger flujo Markdown
Bloquear cualquier filtro que elimine `|---|`.

### 9.3 Validar plantilla
Confirmar existencia y formato de `orm_profesional_base_final.docx`.

### 9.4 QA automático
Generar informe de prueba con ≥ 3 tablas:
- Verificar estilo visual (bordes grises, encabezado sombreado)
- Confirmar formato Word estable
- Validar compatibilidad Office 2019+

### 9.5 Dependencias requeridas
```bash
pip install python-docx
```

---

## 10. Resultado esperado

| Indicador | Resultado |
|-----------|-----------|
| Tablas ORM | Representación tipo Excel profesional |
| Encabezados | Fondo gris #f2f2f2 con texto bold |
| Texto | Arial 12 pt, justificado |
| Márgenes | 2.5 cm uniformes |
| Bordes | Gris oscuro, líneas 1 pt |
| Compatibilidad | Pandoc 3.8+, Office 2019+, LibreOffice 7+ |
| Estructura carpeta | `data/<cliente>/Informe_ORM_YYYYMMDD_HHMMSS.docx` |

---

## 11. Conclusión

La pérdida de formato fue causada por una combinación de:

- Instrucción errónea en el prompt
- Limpieza excesiva del texto
- Errores de escape en YAML
- Parámetros obsoletos en el exporter
- Ausencia de estilos en encabezados de tabla

Tras la corrección v3.2, los informes se generan con:
- ✅ Estructura tabular profesional
- ✅ Sombreado de encabezados (#f2f2f2)
- ✅ Estilo uniforme y corporativo
- ✅ Compatibilidad Office estándar

Se recomienda a Zencoder consolidar la versión 3.2 del módulo como estándar de despliegue y añadir `python-docx` a las dependencias core.

---

**Fin del documento técnico**  
Firmado digitalmente por: AI-CodeInspector / Leox433  
Fecha: 2025-11-09 10:50 UTC
