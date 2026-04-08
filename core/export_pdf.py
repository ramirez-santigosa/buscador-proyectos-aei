"""
Generación de PDF con WeasyPrint (reemplaza win32com.client del .exe original).
Genera un PDF de la hoja "Totales anuales" usando una plantilla HTML/CSS.
"""

from datetime import datetime
from pathlib import Path

from core.search import BusquedaResult

# ── Plantilla HTML ────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  @page {{
    size: A4 landscape;
    margin: 1cm 1.2cm;
    @top-center {{
      content: "AGENCIA ESTATAL DE INVESTIGACIÓN — Búsqueda de Proyectos";
      font-family: Arial, sans-serif; font-size: 8pt; color: #555;
    }}
    @bottom-right {{
      content: "Página " counter(page) " de " counter(pages);
      font-family: Arial, sans-serif; font-size: 7pt; color: #888;
    }}
  }}

  body {{
    font-family: Arial, sans-serif;
    font-size: 8pt;
    color: #222;
    margin: 0;
  }}

  /* ── Cabecera ── */
  .header {{
    display: flex;
    align-items: center;
    background: #DAE3F3;
    padding: 6px 10px;
    margin-bottom: 6px;
    border-bottom: 2px solid #1F4E79;
  }}
  .header-text h1 {{
    margin: 0; font-size: 13pt; color: #053A8B;
  }}
  .header-text h2 {{
    margin: 2px 0 0; font-size: 9pt; font-weight: normal;
    color: #1F4E79; background: #1F4E79; color: white;
    padding: 2px 6px; display: inline-block;
  }}
  .terminos-band {{
    background: #ED7D31; color: white;
    padding: 4px 10px; font-size: 8pt; font-weight: bold;
    margin-bottom: 8px;
  }}

  /* ── Tablas ── */
  .grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 10px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 7.5pt;
  }}
  .tabla-titulo {{
    background: #DAE3F3; color: #053A8B;
    font-weight: bold; font-size: 8pt;
    padding: 3px 5px;
    text-align: center;
  }}
  th {{
    background: #4472C4; color: white;
    padding: 3px 4px; text-align: center;
    font-weight: bold;
  }}
  td {{
    padding: 2px 4px; border-bottom: 1px solid #E0E0E0;
  }}
  tr:nth-child(even) td {{ background: #D9E1F2; }}
  tr.total td {{
    background: #BDD7EE; font-weight: bold;
  }}
  .num {{ text-align: right; }}
  .cen {{ text-align: center; }}

  /* ── Pie ── */
  .footer-note {{
    font-size: 7pt; color: #888; margin-top: 6px; text-align: right;
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-text">
    <h1>AGENCIA ESTATAL DE INVESTIGACIÓN</h1>
    <h2>BÚSQUEDA DE PROYECTOS CONCEDIDOS DESDE 2018</h2>
  </div>
</div>
<div class="terminos-band">
  TÉRMINOS DE LA BÚSQUEDA:&nbsp; {terminos_str}
</div>

<div class="grid">
  <!-- Columna izquierda -->
  <div>
    {tabla_conv}
    <br>
    {tabla_anos}
  </div>

  <!-- Columna derecha -->
  <div>
    {tabla_entidades}
    <br>
    {tabla_ccaa}
  </div>
</div>

<div class="footer-note">
  Generado el {fecha} &nbsp;·&nbsp; {n_proyectos} proyectos &nbsp;·&nbsp;
  Ayuda total: {ayuda_total}
</div>

</body>
</html>
"""


def _fmt_euros(val):
    try:
        return f"{float(val):,.2f} €"
    except Exception:
        return str(val)


def _fmt_int(val):
    try:
        return f"{int(val):,}"
    except Exception:
        return str(val)


def _tabla_html(df, cols, titulo, total_val, col_labels=None, num_cols=None, euro_cols=None):
    """Genera el HTML de una tabla de estadísticas."""
    col_labels = col_labels or {c: c for c in cols}
    num_cols   = num_cols  or []
    euro_cols  = euro_cols or []

    rows_html = []
    for _, row in df.iterrows():
        is_tot = str(row[cols[0]]) == total_val
        cls = ' class="total"' if is_tot else ""
        cells = ""
        for c in cols:
            val = row.get(c, "")
            if c in euro_cols:
                txt = _fmt_euros(val)
                cells += f'<td class="num">{txt}</td>'
            elif c in num_cols:
                txt = _fmt_int(val)
                cells += f'<td class="cen">{txt}</td>'
            else:
                cells += f"<td>{val}</td>"
        rows_html.append(f"<tr{cls}>{cells}</tr>")

    headers = "".join(f"<th>{col_labels.get(c, c)}</th>" for c in cols)
    body    = "\n".join(rows_html)

    return f"""\
<table>
  <tr><td colspan="{len(cols)}" class="tabla-titulo">{titulo}</td></tr>
  <tr>{headers}</tr>
  {body}
</table>"""


def generar_pdf(result: BusquedaResult, out_path: Path, log=print) -> Path:
    """
    Genera el PDF de estadísticas (equivalente a la hoja 'Totales anuales')
    y lo escribe en out_path.
    """
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as e:
        log(f"WeasyPrint no disponible ({e}). PDF no generado.")
        return None

    keywords  = result.keywords
    and_terms = result.and_terms
    and_label = ("  AND: " + " + ".join(and_terms)) if and_terms else ""
    terminos_str = " | ".join(keywords) + and_label

    COLS_T   = ["Año",                   "Proyectos", "Hombres", "Mujeres", "Sin especificar", "Ayuda_Total"]
    COLS_CV  = ["Convocatoria / Programa","Proyectos", "Hombres", "Mujeres", "Sin especificar", "Ayuda_Total"]
    COLS_E   = ["Entidad",               "Proyectos", "Hombres", "Mujeres", "Sin especificar", "Ayuda_Total"]
    COLS_C   = ["Comunidad Autónoma",    "Proyectos", "Hombres", "Mujeres", "Sin especificar", "Ayuda_Total"]

    labels = {
        "Proyectos": "Nº Proy.", "Hombres": "IP Hombre", "Mujeres": "IP Mujer",
        "Sin especificar": "Sin espec.", "Ayuda_Total": "Ayuda (€)",
        "Convocatoria / Programa": "Convocatoria",
    }
    NUM_C  = ["Proyectos", "Hombres", "Mujeres", "Sin especificar"]
    EURO_C = ["Ayuda_Total"]

    tabla_conv      = _tabla_html(result.top_conv,      COLS_CV, "Totales por convocatoria",
                                   "TOTAL", labels, NUM_C, EURO_C)
    tabla_anos      = _tabla_html(result.totales,        COLS_T,  "Totales por año",
                                   "TOTAL", labels, NUM_C, EURO_C)
    tabla_entidades = _tabla_html(result.top_entidades,  COLS_E,  "Top 10 entidades",
                                   "TOTAL TOP 10", labels, NUM_C, EURO_C)
    tabla_ccaa      = _tabla_html(result.top_ccaa,       COLS_C,  "Top 10 Comunidades Autónomas",
                                   "TOTAL TOP 10", labels, NUM_C, EURO_C)

    html = _HTML_TEMPLATE.format(
        terminos_str  = terminos_str,
        tabla_conv    = tabla_conv,
        tabla_anos    = tabla_anos,
        tabla_entidades=tabla_entidades,
        tabla_ccaa    = tabla_ccaa,
        fecha         = datetime.now().strftime("%d/%m/%Y %H:%M"),
        n_proyectos   = f"{result.n_proyectos:,}",
        ayuda_total   = _fmt_euros(result.ayuda_total),
    )

    HTML(string=html).write_pdf(str(out_path))
    log(f"  PDF guardado: {out_path.name}")
    return out_path
