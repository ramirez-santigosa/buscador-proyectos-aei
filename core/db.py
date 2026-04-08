"""
Acceso a SQLite.
La búsqueda usa la columna precalculada `texto_norm` (normalizar aplicado
en ingesta) para que las consultas LIKE sean insensibles a mayúsculas
y tildes sin necesidad de funciones Python en SQLite.
"""

import sqlite3
from pathlib import Path

import pandas as pd

from core.text import normalizar, COL_MAP_DB_TO_CANON, CAMPOS_BUSQUEDA

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "proyectos.db"


def get_connection(db_path=None):
    return sqlite3.connect(str(db_path or DB_PATH))


def buscar_proyectos(keywords, and_terms=None, db_path=None,
                     cif_filter=None, conv_filter=None):
    """
    Busca proyectos en la BD por keywords (OR) con filtro AND opcional.

    Devuelve un DataFrame con columnas canónicas + 'Términos encontrados'.
    Retorna DataFrame vacío si no hay resultados.
    """
    kws_norm = [normalizar(k) for k in keywords if k.strip()]
    if not kws_norm:
        return pd.DataFrame()

    # SQL: OR de texto_norm LIKE ? para cada keyword
    conditions = " OR ".join(["texto_norm LIKE ?"] * len(kws_norm))
    params = [f"%{kw}%" for kw in kws_norm]

    # Filtro CIF en SQL (no necesita normalizar, es un código)
    cif_sql = cif_filter.strip() if cif_filter and cif_filter.strip() else None
    if cif_sql:
        params.append(f"%{cif_sql}%")

    where = f"({conditions})"
    if cif_sql:
        where += " AND upper(nif_cif) LIKE upper(?)"

    sql = f"SELECT * FROM proyectos WHERE {where}"

    con = get_connection(db_path)
    try:
        df = pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()

    if df.empty:
        return pd.DataFrame()

    # Renombrar columnas BD → canónicas y quitar auxiliares
    df = df.rename(columns=COL_MAP_DB_TO_CANON)
    df = df.drop(columns=["id", "texto_norm"], errors="ignore")

    # Filtro convocatoria (Python-side con normalizar para manejar tildes)
    conv_norm = normalizar(conv_filter.strip()) if conv_filter and conv_filter.strip() else None
    if conv_norm:
        df = df[df["Convocatoria / Programa"].apply(
            lambda v: conv_norm in normalizar(str(v) if v is not None else "")
        )]
        if df.empty:
            return pd.DataFrame()

    # Aplicar filtro AND y calcular 'Términos encontrados'
    and_kws_norm = [normalizar(t) for t in (and_terms or []) if t.strip()]

    rows_out = []
    for _, row in df.iterrows():
        texto = " ".join(
            normalizar(str(row.get(c) or "")) for c in CAMPOS_BUSQUEDA
        )
        if and_kws_norm and not all(kw in texto for kw in and_kws_norm):
            continue
        r = row.copy()
        r["Términos encontrados"] = "; ".join(kw for kw in kws_norm if kw in texto)
        rows_out.append(r)

    return pd.DataFrame(rows_out) if rows_out else pd.DataFrame()
