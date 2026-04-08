"""
Generación del Excel de resultados con xlsxwriter.
Portado de buscador_proyectos.py líneas 576-927 + Hoja 3 nueva.

Hojas:
  1. Resultados          — listado completo de proyectos
  2. Totales anuales     — estadísticas (por año, convocatoria, entidad, CCAA)
  3. Desglose por término — nº proyectos y ayuda por término × año (NUEVO)
"""

import tempfile
import textwrap
from datetime import datetime
from pathlib import Path

import pandas as pd
import xlsxwriter

from core.text import COLS_SALIDA
from core.search import BusquedaResult

# ── Paleta corporativa AEI ──────────────────────────────────────
AZUL_OSC = "#1F4E79"
AZUL_MED = "#4472C4"
AZUL_CLR = "#D9E1F2"
AZUL_GRF = "#BDD7EE"
NARANJA  = "#ED7D31"
VERDE    = "#92D050"
BLANCO   = "#FFFFFF"

_LICENCIA = (
    "© Agencia Estatal de Investigación. Buscador de Proyectos AEI. "
    "Licencia CC BY 4.0 https://creativecommons.org/licenses/by/4.0/deed.es "
    "— puedes usar estos datos libremente siempre que menciones la fuente."
)
_FOOTER = f"&L&7{_LICENCIA}"

LOGO_CANDIDATES = [
    Path(__file__).resolve().parents[1] / "web"  / "logo_aei.png",
    Path(__file__).resolve().parents[1] / "data" / "logo_aei.png",
    Path.home() / "OneDrive - MINISTERIO DE CIENCIA E INNOVACIÓN"
    / "General - Unidad de Apoyo" / "08-PROYECTOS"
    / "01-BUSQUEDA DE PROYECTOS" / "SOURCES" / "logo_aei.png",
]


def _logo_path():
    for p in LOGO_CANDIDATES:
        if p.exists():
            return p
    return None


def _cabecera_busqueda(result):
    """Devuelve (terminos_str, filtros_str) listos para mostrar en cabeceras."""
    and_label    = ("  AND: " + " + ".join(result.and_terms)) if result.and_terms else ""
    terminos_str = " | ".join(result.keywords) + and_label
    partes = []
    if result.cif_filter:
        partes.append(f"CIF/NIF: {result.cif_filter}")
    if result.conv_filter:
        partes.append(f"Convocatoria: {result.conv_filter}")
    filtros_str = "  ·  FILTROS:  " + "  |  ".join(partes) if partes else ""
    return terminos_str, filtros_str


def _wrap_terminos(terminos_str, max_chars=80):
    """Divide la cadena de términos en líneas equilibradas para la cabecera."""
    tlen = len(terminos_str)
    if tlen <= max_chars:
        return terminos_str, 1
    nlines = min(3, max(2, tlen // max_chars + 1))
    mid = tlen // nlines
    parts, start = [], 0
    for i in range(nlines):
        if i == nlines - 1:
            parts.append(terminos_str[start:])
        else:
            target = start + (tlen - start) // (nlines - i)
            cut = terminos_str.rfind("|", start, target + 20)
            if cut < 0:
                cut = target
            parts.append(terminos_str[start:cut].strip(" |"))
            start = cut + 1
    return "\n".join(p.strip() for p in parts if p.strip()), nlines


def generar_xlsx(result: BusquedaResult, out_path: Path, log=print) -> Path:
    """Genera el archivo Excel y lo escribe en out_path."""

    terminos_str, filtros_str = _cabecera_busqueda(result)

    wb = xlsxwriter.Workbook(str(out_path), {"constant_memory": False})

    # ── Formatos reutilizables ───────────────────────────────────
    def fmt(bold=False, bg=None, color="#000000", size=9,
            num_fmt=None, align="left", wrap=False, border=1):
        props = {
            "font_name": "Arial", "font_size": size,
            "font_color": color, "bold": bold,
            "align": align, "valign": "vcenter",
            "text_wrap": wrap, "border": border,
        }
        if bg:      props["bg_color"] = bg
        if num_fmt: props["num_format"] = num_fmt
        return wb.add_format(props)

    F_HDR_TITLE = fmt(bold=True, bg="#DAE3F3", color="#053A8B", size=10, align="center")
    F_HDR_COL   = fmt(bold=True, bg=AZUL_MED,  color=BLANCO,    size=9, align="center", wrap=False)
    F_NORMAL    = fmt(bg=BLANCO,  size=9)
    F_ALT       = fmt(bg=AZUL_CLR, size=9)
    F_TOTAL     = fmt(bold=True, bg=AZUL_GRF, size=9)
    F_NUM       = fmt(bg=BLANCO,  size=9, num_fmt="#,##0.00", align="right")
    F_NUM_ALT   = fmt(bg=AZUL_CLR, size=9, num_fmt="#,##0.00", align="right")
    F_NUM_TOT   = fmt(bold=True, bg=AZUL_GRF, size=9, num_fmt="#,##0.00", align="right")
    F_INT       = fmt(bg=BLANCO,  size=9, num_fmt="0", align="center")
    F_INT_ALT   = fmt(bg=AZUL_CLR, size=9, num_fmt="0", align="center")
    F_INT_TOT   = fmt(bold=True, bg=AZUL_GRF, size=9, num_fmt="0", align="center")
    F_AEI       = wb.add_format({"font_name": "Arial", "font_size": 14, "bold": True,
                                  "bg_color": "#DAE3F3", "font_color": "#053A8B",
                                  "align": "center", "valign": "vcenter", "border": 0})
    F_SUB       = wb.add_format({"font_name": "Arial", "font_size": 12, "bold": True,
                                  "bg_color": AZUL_OSC, "font_color": BLANCO,
                                  "align": "center", "valign": "vcenter", "border": 0})

    HDR_MAP = {
        "Año": "Año", "Proyectos": "Nº Proyectos", "Hombres": "IP Hombre",
        "Mujeres": "IP Mujer", "No aplica": "No aplica",
        "Ayuda_Total": "Ayuda Total (€)", "Entidad": "Entidad",
        "Comunidad Autónoma": "Comunidad Autónoma",
        "Convocatoria / Programa": "Convocatoria / Programa",
    }

    ncols = len(COLS_SALIDA)

    # ════════════════════════════════════════════════════════════
    # HOJA 1: Resultados
    # ════════════════════════════════════════════════════════════
    log("  Escribiendo hoja Resultados...")
    ws = wb.add_worksheet("Resultados")
    ws.freeze_panes(2, 0)
    ws.autofilter(1, 0, 1, ncols - 1)

    ws.merge_range(
        0, 0, 0, ncols - 1,
        f'OR: {terminos_str}{filtros_str}  ·  {result.n_proyectos} proyectos  ·  '
        f'Ayuda total: {result.ayuda_total:,.2f} €  ·  {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        F_HDR_TITLE,
    )
    ws.set_row(0, 22)

    for j, col in enumerate(COLS_SALIDA):
        ws.write(1, j, col, F_HDR_COL)
    ws.set_row(1, 28)

    for i, (_, row) in enumerate(result.todos.iterrows()):
        alt = i % 2 == 1
        for j, col in enumerate(COLS_SALIDA):
            val = row[col] if col in row.index else ""
            if col == "Ayuda Total Concedida (€)":
                f = F_NUM_ALT if alt else F_NUM
                try:    ws.write_number(i + 2, j, float(val) if val != "" else 0, f)
                except: ws.write(i + 2, j, val, f)
            else:
                ws.write(i + 2, j, str(val) if val is not None else "", F_ALT if alt else F_NORMAL)

    anchos = [12, 10, 18, 18, 20, 50, 60, 18, 18, 35, 14, 14, 30, 18, 18, 16, 14, 14, 10, 18, 25]
    for j, a in enumerate(anchos):
        ws.set_column(j, j, a)
    ws.set_footer(_FOOTER)

    # ════════════════════════════════════════════════════════════
    # HOJA 2: Totales anuales
    # ════════════════════════════════════════════════════════════
    log("  Escribiendo hoja Totales anuales...")
    ws2 = wb.add_worksheet("Totales anuales")
    ws2.set_landscape()
    ws2.set_paper(9)
    ws2.set_margins(left=0.3, right=0.3, top=0.3, bottom=0.3)
    ws2.fit_to_pages(1, 1)

    # Calcular fuente/altura para la fila de términos
    _tlen = len(terminos_str)
    if _tlen <= 80:    _tfont, _theight = 10, 22
    elif _tlen <= 180: _tfont, _theight = 9,  36
    elif _tlen <= 320: _tfont, _theight = 8,  36
    elif _tlen <= 480: _tfont, _theight = 8,  52
    else:              _tfont, _theight = 7,  52

    terminos_display, _ = _wrap_terminos(terminos_str, max_chars=int(1100 / (_tfont * 0.65)))

    F_TERMS = wb.add_format({
        "font_name": "Arial", "font_size": _tfont, "bold": True,
        "bg_color": NARANJA, "font_color": BLANCO,
        "align": "center", "valign": "vcenter", "border": 0, "text_wrap": True,
    })

    # Anchos columnas (layout apaisado: izquierda cols 0-5, separador col 6, derecha cols 7-12)
    ws2.set_column(0, 0, 28); ws2.set_column(1, 1, 13); ws2.set_column(2, 2, 11)
    ws2.set_column(3, 3, 11); ws2.set_column(4, 4, 12); ws2.set_column(5, 5, 15)
    ws2.set_column(6, 6, 2)   # separador
    ws2.set_column(7, 7, 30); ws2.set_column(8, 8, 13); ws2.set_column(9, 9, 11)
    ws2.set_column(10, 10, 11); ws2.set_column(11, 11, 12); ws2.set_column(12, 12, 15)

    # Cabecera institucional (filas 0-2)
    # Calcular altura real de fila 2 primero para escalar el logo correctamente
    _row2_h = _theight + (12 if filtros_str else 0)
    # Logo: 1755×1234 px. En Excel 1pt = 4/3 px (96 DPI).
    # Escala para que el logo ocupe exactamente las 3 filas (0+1+2).
    _logo_scale = round((26 + 22 + _row2_h) * (4 / 3) / 1234, 4)

    F_LOGO_BG = wb.add_format({"bg_color": "#DAE3F3", "border": 0})
    ws2.merge_range(0, 0, 2, 0, "", F_LOGO_BG)
    logo = _logo_path()
    if logo:
        ws2.insert_image(0, 0, str(logo),
                         {"x_scale": _logo_scale, "y_scale": _logo_scale,
                          "x_offset": 2, "y_offset": 2,
                          "object_position": 2})
    ws2.merge_range(0, 1, 0, 12, "AGENCIA ESTATAL DE INVESTIGACIÓN", F_AEI)
    ws2.set_row(0, 26)
    ws2.merge_range(1, 1, 1, 12, "BÚSQUEDA DE PROYECTOS CONCEDIDOS DESDE 2018", F_SUB)
    ws2.set_row(1, 22)
    terms_cell = f"TÉRMINOS DE LA BÚSQUEDA:  {terminos_display}"
    if filtros_str:
        terms_cell += f"\n{filtros_str.strip(' ·').strip()}"
    ws2.merge_range(2, 1, 2, 12, terms_cell, F_TERMS)
    ws2.set_row(2, _row2_h)

    # Fila 3: licencia (antes de las tablas)
    F_LIC = wb.add_format({
        "font_name": "Arial", "font_size": 7, "italic": True,
        "font_color": "#888888", "border": 0, "align": "left", "valign": "vcenter",
    })
    ws2.merge_range(3, 0, 3, 12, _LICENCIA, F_LIC)
    ws2.set_row(3, 11)

    COLS_T  = ["Año", "Proyectos", "Hombres", "Mujeres", "No aplica", "Ayuda_Total"]
    COLS_CV = ["Convocatoria / Programa", "Proyectos", "Hombres", "Mujeres", "No aplica", "Ayuda_Total"]
    COLS_E  = ["Entidad", "Proyectos", "Hombres", "Mujeres", "No aplica", "Ayuda_Total"]
    COLS_C  = ["Comunidad Autónoma", "Proyectos", "Hombres", "Mujeres", "No aplica", "Ayuda_Total"]

    def escribir_tabla_col(ws, df, cols, start_row, titulo, total_val, col_offset=0):
        ncols_t = len(cols)
        ws.merge_range(start_row, col_offset, start_row, col_offset + ncols_t - 1, titulo, F_HDR_TITLE)
        ws.set_row(start_row, 16)
        hdr_row = start_row + 1
        for j, col in enumerate(cols):
            ws.write(hdr_row, col_offset + j, HDR_MAP.get(col, col), F_HDR_COL)
        ws.set_row(hdr_row, 16)
        data_row = hdr_row + 1
        for i, (_, row) in enumerate(df.iterrows()):
            ws.set_row(data_row + i, 16)
            alt = i % 2 == 1
            is_tot = str(row[cols[0]]) == total_val
            for j, col in enumerate(cols):
                val = row[col] if col in row.index else ""
                if is_tot:
                    f = F_NUM_TOT if col == "Ayuda_Total" else (
                        F_INT_TOT if col in ("Proyectos", "Hombres", "Mujeres", "No aplica")
                        else F_TOTAL)
                elif alt:
                    f = F_NUM_ALT if col == "Ayuda_Total" else (
                        F_INT_ALT if col in ("Proyectos", "Hombres", "Mujeres", "No aplica")
                        else F_ALT)
                else:
                    f = F_NUM if col == "Ayuda_Total" else (
                        F_INT if col in ("Proyectos", "Hombres", "Mujeres", "No aplica")
                        else F_NORMAL)
                if col == "Ayuda_Total":
                    try:    ws.write_number(data_row + i, col_offset + j, float(val) if val != "" else 0, f)
                    except: ws.write(data_row + i, col_offset + j, val, f)
                elif col in ("Proyectos", "Hombres", "Mujeres", "No aplica"):
                    try:    ws.write_number(data_row + i, col_offset + j, int(val) if val != "" else 0, f)
                    except: ws.write(data_row + i, col_offset + j, val, f)
                else:
                    display = "2025 *" if col == "Año" and val == 2025 else (str(val) if val is not None else "")
                    ws.write(data_row + i, col_offset + j, display, f)
        return data_row + len(df)

    # Columna izquierda: convocatorias + años
    row_izq = escribir_tabla_col(ws2, result.top_conv, COLS_CV, 4,
                                  "Totales por convocatoria", "TOTAL", col_offset=0)
    row_ano_start = row_izq + 1
    row_izq = escribir_tabla_col(ws2, result.totales, COLS_T, row_ano_start,
                                  "Totales por año de convocatoria", "TOTAL", col_offset=0)
    F_NOTA2025 = wb.add_format({"font_name": "Arial", "font_size": 7, "italic": True,
                                 "font_color": "#666666", "border": 0, "align": "left"})
    ws2.merge_range(row_izq, 0, row_izq, 5, "* 2025: Convocatorias pendientes de resolver", F_NOTA2025)
    ws2.set_row(row_izq, 11)
    row_izq += 1

    # Gráfico debajo de la tabla de años
    totales_data = result.totales[result.totales["Año"] != "TOTAL"]
    n_data = len(totales_data)
    data_ini = row_ano_start + 2
    data_fin = data_ini + n_data - 1

    chart = wb.add_chart({"type": "column"})
    chart.add_series({
        "name": "Nº Proyectos", "fill": {"color": AZUL_MED}, "gap": 100,
        "categories": ["Totales anuales", data_ini, 0, data_fin, 0],
        "values":     ["Totales anuales", data_ini, 1, data_fin, 1],
    })
    chart.add_series({
        "name": "IP Hombre", "fill": {"color": NARANJA},
        "categories": ["Totales anuales", data_ini, 0, data_fin, 0],
        "values":     ["Totales anuales", data_ini, 2, data_fin, 2],
    })
    chart.add_series({
        "name": "IP Mujer", "fill": {"color": VERDE},
        "categories": ["Totales anuales", data_ini, 0, data_fin, 0],
        "values":     ["Totales anuales", data_ini, 3, data_fin, 3],
    })
    titulo_corto = "Proyectos AEI desde 2018  |  " + (
        terminos_str if len(terminos_str) <= 60 else terminos_str[:57] + "..."
    )
    chart.set_title({"name": titulo_corto, "name_font": {"size": 9, "bold": True}})
    chart.set_x_axis({"num_format": "0", "num_font": {"size": 8},
                      "major_gridlines": {"visible": False}, "text_axis": True})
    chart.set_y_axis({"name": "Nº Proyectos", "name_font": {"size": 8}})
    chart.set_legend({"position": "bottom", "font": {"size": 8}})
    chart.set_size({"width": 420, "height": 250})
    chart.set_style(10)
    ws2.insert_chart(row_izq + 1, 0, chart, {"x_offset": 84, "y_offset": 5})

    # Columna derecha: entidades + CCAA
    row_der = escribir_tabla_col(ws2, result.top_entidades, COLS_E, 4,
                                  "Top 10 entidades con más proyectos", "TOTAL TOP 10", col_offset=7)
    row_ccaa_start = row_der + 1
    row_der = escribir_tabla_col(ws2, result.top_ccaa, COLS_C, row_ccaa_start,
                                  "Top 10 Comunidades Autónomas con más proyectos", "TOTAL TOP 10",
                                  col_offset=7)

    # Mapa CCAA (si está disponible)
    try:
        from core.maps import generar_mapa_ccaa
        map_tmp = Path(tempfile.gettempdir()) / "mapa_ccaa_tmp.png"
        map_ok = generar_mapa_ccaa(result.todas_ccaa, map_tmp, terminos_str)
        if map_ok and map_tmp.exists():
            ws2.insert_image(row_der + 1, 7, str(map_tmp),
                             {"x_scale": 1.0, "y_scale": 1.0, "x_offset": 30, "y_offset": 0})
            log("  Mapa de CCAA generado.")
    except Exception as e:
        log(f"  Mapa no generado: {e}")

    ws2.fit_to_pages(1, 1)
    ws2.set_footer(_FOOTER)

    # ════════════════════════════════════════════════════════════
    # HOJA 3: Desglose por término  (NUEVA)
    # ════════════════════════════════════════════════════════════
    log("  Escribiendo hoja Desglose por término...")
    _escribir_hoja_desglose(wb, result, terminos_str, filtros_str, F_HDR_TITLE, F_HDR_COL,
                             F_NORMAL, F_ALT, F_TOTAL, F_NUM, F_NUM_ALT, F_NUM_TOT,
                             F_INT, F_INT_ALT, F_INT_TOT)

    wb.close()
    log(f"  Excel guardado: {out_path.name}")
    return out_path


def _escribir_hoja_desglose(wb, result, terminos_str, filtros_str,
                             F_HDR_TITLE, F_HDR_COL, F_NORMAL, F_ALT, F_TOTAL,
                             F_NUM, F_NUM_ALT, F_NUM_TOT, F_INT, F_INT_ALT, F_INT_TOT):
    """Escribe la hoja 'Desglose por término'."""

    df_p = result.df_terminos_proyectos   # nº proyectos
    df_a = result.df_terminos_ayuda       # ayuda total

    if df_p.empty:
        return

    ws = wb.add_worksheet("Desglose por término")
    ws.set_footer(_FOOTER)

    F_TITULO_HOJA = wb.add_format({
        "font_name": "Arial", "font_size": 13, "bold": True,
        "bg_color": "#053A8B", "font_color": "#FFFFFF",
        "align": "center", "valign": "vcenter", "border": 0,
    })
    F_SUBTITULO = wb.add_format({
        "font_name": "Arial", "font_size": 9,
        "bg_color": "#ED7D31", "font_color": "#FFFFFF",
        "align": "left", "valign": "vcenter", "border": 0, "text_wrap": True,
    })
    F_NOTA = wb.add_format({
        "font_name": "Arial", "font_size": 8, "italic": True,
        "font_color": "#666666", "border": 0, "align": "left",
    })
    F_SECCION = wb.add_format({
        "font_name": "Arial", "font_size": 11, "bold": True,
        "bg_color": "#1F4E79", "font_color": "#FFFFFF",
        "align": "left", "valign": "vcenter", "border": 0,
    })

    # Columnas: Término + años + TOTAL
    year_cols = [c for c in df_p.columns if c not in ("Término",)]
    ncols_tabla = 1 + len(year_cols)  # Término + años + TOTAL

    # Ancho columna Término: proporcional al keyword más largo
    max_kw_len = max((len(k) for k in result.keywords), default=10)
    ws.set_column(0, 0, max(18, min(max_kw_len + 4, 40)))
    for j in range(1, ncols_tabla):
        col_name = year_cols[j - 1]
        ws.set_column(j, j, 14 if col_name == "TOTAL" else 10)

    # ── Fila 0: título de la hoja ──
    ws.merge_range(0, 0, 0, ncols_tabla - 1,
                   "DESGLOSE DE RESULTADOS POR TÉRMINO DE BÚSQUEDA", F_TITULO_HOJA)
    ws.set_row(0, 28)

    # ── Fila 1: términos buscados + filtros ──
    busqueda_cell = f"Búsqueda:  {terminos_str}"
    if filtros_str:
        busqueda_cell += f"   {filtros_str.strip()}"
    ws.merge_range(1, 0, 1, ncols_tabla - 1, busqueda_cell, F_SUBTITULO)
    ws.set_row(1, 20 if not filtros_str else 30)

    # ── Fila 2: nota ──
    ws.merge_range(2, 0, 2, ncols_tabla - 1,
                   "* Un mismo proyecto puede contener varios términos y aparece en cada uno de ellos.",
                   F_NOTA)
    ws.set_row(2, 16)

    def _escribir_tabla_terminos(df, start_row, titulo_seccion, is_ayuda):
        """Escribe una tabla de desglose por término."""
        # Fila sección
        ws.merge_range(start_row, 0, start_row, ncols_tabla - 1, titulo_seccion, F_SECCION)
        ws.set_row(start_row, 20)

        # Cabecera
        hdr_row = start_row + 1
        ws.write(hdr_row, 0, "Término", F_HDR_COL)
        for j, col in enumerate(year_cols, start=1):
            label = "2025 *" if col == "2025" else col
            ws.write(hdr_row, j, label, F_HDR_COL)
        ws.set_row(hdr_row, 22)

        # Datos
        data_row = hdr_row + 1
        for i, (_, row) in enumerate(df.iterrows()):
            alt = i % 2 == 1
            ws.set_row(data_row + i, 16)

            # Columna Término
            ws.write(data_row + i, 0, str(row["Término"]), F_ALT if alt else F_NORMAL)

            # Columnas numéricas
            for j, col in enumerate(year_cols, start=1):
                val = row.get(col, 0) or 0
                if is_ayuda:
                    f = F_NUM_ALT if alt else F_NUM
                    try:    ws.write_number(data_row + i, j, float(val), f)
                    except: ws.write(data_row + i, j, val, f)
                else:
                    f = F_INT_ALT if alt else F_INT
                    try:    ws.write_number(data_row + i, j, int(val), f)
                    except: ws.write(data_row + i, j, val, f)

        # Fila TOTALES (suma de columnas — solo informativo)
        tot_row = data_row + len(df)
        ws.set_row(tot_row, 16)
        ws.write(tot_row, 0, "SUMA (puede incluir duplicados)", F_TOTAL)
        for j, col in enumerate(year_cols, start=1):
            total_val = df[col].apply(pd.to_numeric, errors="coerce").sum()
            if is_ayuda:
                try:    ws.write_number(tot_row, j, float(total_val), F_NUM_TOT)
                except: ws.write(tot_row, j, total_val, F_NUM_TOT)
            else:
                try:    ws.write_number(tot_row, j, int(total_val), F_INT_TOT)
                except: ws.write(tot_row, j, total_val, F_INT_TOT)

        return tot_row + 1

    F_NOTA_DES = wb.add_format({"font_name": "Arial", "font_size": 7, "italic": True,
                                 "font_color": "#666666", "border": 0, "align": "left"})
    _NOTA_2025_TXT = "* 2025: Convocatorias pendientes de resolver"

    # Tabla 1: Nº Proyectos
    next_row = _escribir_tabla_terminos(
        df_p, start_row=4,
        titulo_seccion="Nº de Proyectos por término y año de convocatoria",
        is_ayuda=False,
    )
    ws.merge_range(next_row, 0, next_row, ncols_tabla - 1, _NOTA_2025_TXT, F_NOTA_DES)
    ws.set_row(next_row, 10)

    # Espacio entre tablas
    ws.set_row(next_row + 1, 10)

    # Tabla 2: Ayuda Total
    next_row2 = _escribir_tabla_terminos(
        df_a, start_row=next_row + 2,
        titulo_seccion="Presupuesto Total Concedido (€) por término y año de convocatoria",
        is_ayuda=True,
    )
    ws.merge_range(next_row2, 0, next_row2, ncols_tabla - 1, _NOTA_2025_TXT, F_NOTA_DES)
    ws.set_row(next_row2, 10)
