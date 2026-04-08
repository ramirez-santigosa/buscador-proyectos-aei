"""
Generación de PDF con WeasyPrint (reemplaza win32com.client del .exe original).
Genera un PDF de la hoja "Totales anuales" usando una plantilla HTML/CSS.
"""

import base64
from datetime import datetime
from pathlib import Path

from core.search import BusquedaResult

_REPO = Path(__file__).resolve().parents[1]
_LOGO_CANDIDATES = [
    _REPO / "web" / "logo_aei.png",
    _REPO / "data" / "logo_aei.png",
]

def _logo_b64():
    for p in _LOGO_CANDIDATES:
        if p.exists():
            return base64.b64encode(p.read_bytes()).decode()
    return None


def _chart_b64(totales_df):
    """Gráfico de barras proyectos/IP por año como PNG base64."""
    try:
        import io
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df = totales_df[totales_df["Año"].astype(str) != "TOTAL"].copy()
        if df.empty:
            return None
        anos  = [str(a) for a in df["Año"]]
        x     = list(range(len(anos)))
        w     = 0.28

        fig, ax = plt.subplots(figsize=(5.5, 2.8))
        fig.patch.set_facecolor("#F8FBFF")
        ax.set_facecolor("#F8FBFF")
        ax.bar([i - w for i in x], df["Proyectos"], width=w, label="Nº Proyectos", color="#4472C4")
        ax.bar(x,            df["Hombres"],   width=w, label="IP Hombre",    color="#ED7D31")
        ax.bar([i + w for i in x], df["Mujeres"],   width=w, label="IP Mujer",     color="#70AD47")
        ax.set_xticks(x)
        ax.set_xticklabels(anos, fontsize=7)
        ax.tick_params(axis="y", labelsize=7)
        ax.legend(fontsize=7, loc="upper left")
        ax.spines[["top", "right"]].set_visible(False)
        plt.tight_layout(pad=0.4)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except Exception:
        return None


def _mapa_b64(todas_ccaa_df, terminos_str):
    """Mapa CCAA como PNG base64 (dpi bajo para PDF)."""
    try:
        import tempfile
        from core.maps import generar_mapa_ccaa
        tmp = Path(tempfile.gettempdir()) / "mapa_pdf_tmp.png"
        if generar_mapa_ccaa(todas_ccaa_df, tmp, terminos_str, dpi=150):
            data = base64.b64encode(tmp.read_bytes()).decode()
            tmp.unlink(missing_ok=True)
            return data
    except Exception:
        pass
    return None

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
    gap: 12px;
  }}
  .header-logo {{
    height: 48px; width: auto; flex-shrink: 0;
  }}
  .header-text h1 {{
    margin: 0; font-size: 13pt; color: #053A8B;
  }}
  .header-text h2 {{
    margin: 2px 0 0; font-size: 9pt; font-weight: normal;
    background: #1F4E79; color: white;
    padding: 2px 6px; display: inline-block;
  }}
  .terminos-band {{
    background: #ED7D31; color: white;
    padding: 4px 10px; font-size: 8pt; font-weight: bold;
    margin-bottom: 8px;
  }}
  .filtros-band {{
    background: #F4EDDE; color: #7B3D00;
    padding: 3px 10px; font-size: 7.5pt;
    margin-top: -7px; margin-bottom: 8px;
    border-left: 3px solid #ED7D31;
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

  /* ── Figuras ── */
  .fig-img {{
    width: 100%; margin-top: 6px; display: block;
  }}

  /* ── Pie ── */
  .footer-note {{
    font-size: 7pt; color: #888; margin-top: 6px; text-align: right;
  }}
  .footer-licencia {{
    font-size: 6.5pt; color: #aaa; margin-top: 3px; text-align: left;
  }}
</style>
</head>
<body>

<div class="header">
  {logo_tag}
  <div class="header-text">
    <h1>AGENCIA ESTATAL DE INVESTIGACIÓN</h1>
    <h2>BÚSQUEDA DE PROYECTOS CONCEDIDOS DESDE 2018</h2>
  </div>
</div>
<div class="terminos-band">
  TÉRMINOS DE LA BÚSQUEDA:&nbsp; {terminos_str}
</div>
{filtros_band}

<div class="grid">
  <!-- Columna izquierda: convocatorias + años + gráfico -->
  <div>
    {tabla_conv}
    <br>
    {tabla_anos}
    {chart_img}
  </div>

  <!-- Columna derecha: entidades + CCAA + mapa -->
  <div>
    {tabla_entidades}
    <br>
    {tabla_ccaa}
    {mapa_img}
  </div>
</div>

<div class="footer-note">
  Generado el {fecha} &nbsp;·&nbsp; {n_proyectos} proyectos &nbsp;·&nbsp;
  Ayuda total: {ayuda_total}
</div>
<div class="footer-licencia">
  © Agencia Estatal de Investigación. Buscador de Proyectos AEI.
  Licencia CC BY 4.0 https://creativecommons.org/licenses/by/4.0/deed.es
  — puedes usar estos datos libremente siempre que menciones la fuente.
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
    filtros_parts = []
    if result.cif_filter:
        filtros_parts.append(f"CIF/NIF: {result.cif_filter}")
    if result.conv_filter:
        filtros_parts.append(f"Convocatoria: {result.conv_filter}")
    filtros_str = ("  ·  FILTROS:  " + "  |  ".join(filtros_parts)) if filtros_parts else ""

    logo_b64 = _logo_b64()
    logo_tag = (
        f'<img src="data:image/png;base64,{logo_b64}" class="header-logo" alt="Logo AEI">'
        if logo_b64 else ""
    )

    chart_b64 = _chart_b64(result.totales)
    chart_img = (
        f'<img src="data:image/png;base64,{chart_b64}" class="fig-img" alt="Gráfico por año">'
        if chart_b64 else ""
    )

    mapa_b64 = _mapa_b64(result.todas_ccaa, terminos_str)
    mapa_img = (
        f'<img src="data:image/png;base64,{mapa_b64}" class="fig-img" alt="Mapa CCAA">'
        if mapa_b64 else ""
    )

    COLS_T   = ["Año",                   "Proyectos", "Hombres", "Mujeres", "No aplica", "Ayuda_Total"]
    COLS_CV  = ["Convocatoria / Programa","Proyectos", "Hombres", "Mujeres", "No aplica", "Ayuda_Total"]
    COLS_E   = ["Entidad",               "Proyectos", "Hombres", "Mujeres", "No aplica", "Ayuda_Total"]
    COLS_C   = ["Comunidad Autónoma",    "Proyectos", "Hombres", "Mujeres", "No aplica", "Ayuda_Total"]

    labels = {
        "Proyectos": "Nº Proy.", "Hombres": "IP Hombre", "Mujeres": "IP Mujer",
        "No aplica": "No aplica", "Ayuda_Total": "Ayuda (€)",
        "Convocatoria / Programa": "Convocatoria",
    }
    NUM_C  = ["Proyectos", "Hombres", "Mujeres", "No aplica"]
    EURO_C = ["Ayuda_Total"]

    tabla_conv      = _tabla_html(result.top_conv,      COLS_CV, "Totales por convocatoria",
                                   "TOTAL", labels, NUM_C, EURO_C)
    tabla_anos      = _tabla_html(result.totales,        COLS_T,  "Totales por año",
                                   "TOTAL", labels, NUM_C, EURO_C)
    tabla_entidades = _tabla_html(result.top_entidades,  COLS_E,  "Top 10 entidades",
                                   "TOTAL TOP 10", labels, NUM_C, EURO_C)
    tabla_ccaa      = _tabla_html(result.top_ccaa,       COLS_C,  "Top 10 Comunidades Autónomas",
                                   "TOTAL TOP 10", labels, NUM_C, EURO_C)

    filtros_band = (
        f'<div class="filtros-band">{filtros_str.strip(" ·").strip()}</div>'
        if filtros_str else ""
    )

    html = _HTML_TEMPLATE.format(
        logo_tag      = logo_tag,
        chart_img     = chart_img,
        mapa_img      = mapa_img,
        terminos_str  = terminos_str,
        filtros_band  = filtros_band,
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
