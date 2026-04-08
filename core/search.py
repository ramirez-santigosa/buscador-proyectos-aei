"""
Lógica de búsqueda y agregaciones.
Refactor de buscar() del .exe original, ahora lee de SQLite.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from core.db import buscar_proyectos
from core.text import normalizar, COLS_SALIDA


@dataclass
class BusquedaResult:
    todos: pd.DataFrame           # todas las filas resultado (COLS_SALIDA)
    todos_stats: pd.DataFrame     # deduplicado por proyecto (para estadísticas)
    totales: pd.DataFrame         # agregado por año (con fila TOTAL)
    top_conv: pd.DataFrame        # por convocatoria (con fila TOTAL)
    top_entidades: pd.DataFrame   # top 10 entidades (con fila TOTAL TOP 10)
    top_ccaa: pd.DataFrame        # top 10 CCAA (con fila TOTAL TOP 10)
    todas_ccaa: pd.DataFrame      # todas las CCAA (para el mapa)
    df_terminos_proyectos: pd.DataFrame  # desglose nº proyectos por término × año
    df_terminos_ayuda: pd.DataFrame      # desglose ayuda total por término × año
    ayuda_total: float
    n_proyectos: int
    keywords: list[str]
    and_terms: list[str]


def _agg(df, group_col):
    """Agrega un DataFrame por group_col → Proyectos, Ayuda_Total, Hombres, Mujeres, No aplica."""
    g = df.groupby(group_col, dropna=False)
    result = g.agg(
        Proyectos=("Referencia", "count"),
        Ayuda_Total=(
            "Ayuda Total Concedida (€)",
            lambda x: pd.to_numeric(x, errors="coerce").sum(),
        ),
    ).reset_index()
    result["Hombres"]         = g["_genero"].apply(lambda s: (s == "HOMBRE").sum()).values
    result["Mujeres"]         = g["_genero"].apply(lambda s: (s == "MUJER").sum()).values
    result["No aplica"] = g["_genero"].apply(
        lambda s: (~s.isin(["HOMBRE", "MUJER"])).sum()
    ).values
    return result


def _fila_total(df, label_col, label_val):
    return pd.DataFrame([{
        label_col:        label_val,
        "Proyectos":      df["Proyectos"].sum(),
        "Ayuda_Total":    df["Ayuda_Total"].sum(),
        "Hombres":        df["Hombres"].sum(),
        "Mujeres":        df["Mujeres"].sum(),
        "No aplica":df["No aplica"].sum(),
    }])


def _calcular_desglose_terminos(todos_stats, keywords, kws_norm):
    """
    Para cada término (OR) calcula:
      - Nº proyectos únicos que lo contienen, por año y total
      - Ayuda total de esos proyectos, por año y total

    Retorna (df_proyectos, df_ayuda) con estructura:
        Término | año1 | año2 | ... | TOTAL
    """
    cp = todos_stats.copy()
    cp["_ano_int"] = pd.to_numeric(cp["Año Convocatoria"], errors="coerce")
    anos = sorted(cp["_ano_int"].dropna().unique().astype(int).tolist())

    rows_p, rows_a = [], []

    for kw_orig, kw_norm in zip(keywords, kws_norm):
        # Filas donde el término normalizado aparece en 'Términos encontrados'
        mask = cp["Términos encontrados"].apply(
            lambda t: kw_norm in [x.strip() for x in str(t).split(";")]
        )
        df_kw = cp[mask]

        row_p = {"Término": kw_orig}
        row_a = {"Término": kw_orig}
        total_p, total_a = 0, 0.0

        for ano in anos:
            df_ano = df_kw[df_kw["_ano_int"] == ano]
            n = len(df_ano)
            a = pd.to_numeric(df_ano["Ayuda Total Concedida (€)"], errors="coerce").sum()
            row_p[str(ano)] = n
            row_a[str(ano)] = float(a)
            total_p += n
            total_a += float(a)

        row_p["TOTAL"] = total_p
        row_a["TOTAL"] = total_a
        rows_p.append(row_p)
        rows_a.append(row_a)

    cols = ["Término"] + [str(a) for a in anos] + ["TOTAL"]
    df_p = pd.DataFrame(rows_p, columns=cols) if rows_p else pd.DataFrame(columns=cols)
    df_a = pd.DataFrame(rows_a, columns=cols) if rows_a else pd.DataFrame(columns=cols)
    return df_p, df_a


def buscar(keywords, and_terms=None, db_path=None, log=print, progreso=None):
    """
    Ejecuta la búsqueda completa y devuelve un BusquedaResult.
    Retorna None si no hay resultados.
    """
    kws_norm = [normalizar(k) for k in keywords if k.strip()]
    keywords_clean = [k for k in keywords if k.strip()]

    log("Buscando en la base de datos...")
    todos = buscar_proyectos(keywords_clean, and_terms=and_terms, db_path=db_path)

    if todos is None or todos.empty:
        log("No se encontraron proyectos.")
        return None

    if progreso:
        progreso(0.6)

    # Asegurar todas las columnas canónicas
    for col in COLS_SALIDA:
        if col not in todos.columns:
            todos[col] = ""
    todos = todos[COLS_SALIDA]

    # ── Deduplicar por proyecto para estadísticas ──
    todos_stats = todos.copy()
    todos_stats["_ref_proj"] = todos_stats.apply(
        lambda r: r["Referencia Padre"]
        if pd.notna(r["Referencia Padre"]) and str(r["Referencia Padre"]).strip()
        else r["Referencia"],
        axis=1,
    )
    todos_stats = todos_stats.drop_duplicates(subset=["_ref_proj"])
    todos_stats["_ano"] = pd.to_numeric(todos_stats["Año Convocatoria"], errors="coerce")
    todos_stats["_genero"] = todos_stats["Género"].fillna("").str.upper().str.strip()

    ayuda_total = pd.to_numeric(
        todos_stats["Ayuda Total Concedida (€)"], errors="coerce"
    ).sum()
    n_proyectos = len(todos_stats)

    log(f"Total proyectos: {n_proyectos} | Ayuda total: {ayuda_total:,.2f} €")
    if progreso:
        progreso(0.7)

    # ── Totales por año ──
    totales = _agg(todos_stats, "_ano").rename(columns={"_ano": "Año"}).sort_values("Año")
    totales["Año"] = totales["Año"].apply(
        lambda x: int(x) if pd.notna(x) and x != "" else "Sin año"
    )
    totales = pd.concat([totales, _fila_total(totales, "Año", "TOTAL")], ignore_index=True)

    # ── Top por convocatoria ──
    top_conv = _agg(todos_stats, "Convocatoria / Programa").rename(
        columns={"Convocatoria / Programa": "Convocatoria / Programa"}
    )
    top_conv["Convocatoria / Programa"] = top_conv["Convocatoria / Programa"].replace("", "Sin clasificar")
    top_conv = top_conv.sort_values("Ayuda_Total", ascending=False).reset_index(drop=True)
    top_conv = pd.concat([top_conv, _fila_total(top_conv, "Convocatoria / Programa", "TOTAL")], ignore_index=True)

    # ── Top 10 entidades ──
    top_ent = _agg(todos_stats, "Organismo / Entidad").rename(
        columns={"Organismo / Entidad": "Entidad"}
    )
    top_ent = (
        top_ent[top_ent["Entidad"] != ""]
        .sort_values("Ayuda_Total", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )
    top_ent = pd.concat([top_ent, _fila_total(top_ent, "Entidad", "TOTAL TOP 10")], ignore_index=True)

    # ── Top 10 CCAA ──
    todas_ccaa = _agg(todos_stats, "Comunidad Autónoma").rename(
        columns={"Comunidad Autónoma": "Comunidad Autónoma"}
    )
    top_ccaa = (
        todas_ccaa[todas_ccaa["Comunidad Autónoma"] != ""]
        .sort_values("Ayuda_Total", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )
    top_ccaa = pd.concat(
        [top_ccaa, _fila_total(top_ccaa, "Comunidad Autónoma", "TOTAL TOP 10")],
        ignore_index=True,
    )

    if progreso:
        progreso(0.85)

    # ── Desglose por término ──
    df_tp, df_ta = _calcular_desglose_terminos(todos_stats, keywords_clean, kws_norm)

    log("Agregaciones completadas.")
    if progreso:
        progreso(0.9)

    return BusquedaResult(
        todos=todos,
        todos_stats=todos_stats,
        totales=totales,
        top_conv=top_conv,
        top_entidades=top_ent,
        top_ccaa=top_ccaa,
        todas_ccaa=todas_ccaa,
        df_terminos_proyectos=df_tp,
        df_terminos_ayuda=df_ta,
        ayuda_total=float(ayuda_total),
        n_proyectos=n_proyectos,
        keywords=keywords_clean,
        and_terms=[t for t in (and_terms or []) if t.strip()],
    )
