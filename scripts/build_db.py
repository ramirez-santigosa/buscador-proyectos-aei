"""
build_db.py — Ingesta de FUENTES_DE_DATOS/ → data/proyectos.db

Uso:
    python scripts/build_db.py
    python scripts/build_db.py --fuentes C:/ruta/a/FUENTES_DE_DATOS

Lee todos los CSVs de ANUALES/ y los Excels de RTC-CPP-PLE/, normaliza columnas,
deduplica (RTC tiene prioridad), y escribe data/proyectos.db con índice FTS5.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

# Añadir raíz del repo al path para importar core
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.text import (
    MAPA_CSV, MAPA_EXCEL, COLS_SALIDA,
    normalizar, normalizar_numero, limpiar, detectar_programa,
)

DB_PATH = REPO / "data" / "proyectos.db"

# Columnas que se almacenan en la BD (excluimos "Términos encontrados",
# que se calcula en tiempo de búsqueda)
COLS_BD = [c for c in COLS_SALIDA if c != "Términos encontrados"]

# --------------------------------------------------------------
# Lectura de fuentes (sin filtro de keywords)
# --------------------------------------------------------------

def leer_excel(path: Path, log) -> pd.DataFrame:
    programa = detectar_programa(path.name)
    log(f"  {path.name}")
    try:
        df = pd.read_excel(path, dtype=str)
    except Exception as e:
        log(f"    ERROR: {e}")
        return pd.DataFrame()

    df.columns = [normalizar(c) for c in df.columns]
    df = df.rename(columns={c: MAPA_EXCEL[c] for c in df.columns if c in MAPA_EXCEL})

    if "Prioridad Temática / Reto / Área" not in df.columns and "_reto" in df.columns:
        df["Prioridad Temática / Reto / Área"] = df["_reto"]
    if "_area" in df.columns:
        df["Área / Subárea"] = df["_area"].fillna("") + df.apply(
            lambda r: " / " + r["_subarea"]
            if "_subarea" in df.columns and pd.notna(r.get("_subarea")) and r.get("_subarea")
            else "",
            axis=1,
        )

    df["Fuente"] = "RTC-CPP-PLE"
    if "_convocatoria" in df.columns:
        df["Convocatoria / Programa"] = df["_convocatoria"].fillna(programa)
        df = df.drop(columns=["_convocatoria"], errors="ignore")
    else:
        df["Convocatoria / Programa"] = programa
    df["Género"] = ""

    for col in ["Título", "Resumen"]:
        if col in df.columns:
            df[col] = df[col].apply(limpiar)
    if "Ayuda Total Concedida (€)" in df.columns:
        df["Ayuda Total Concedida (€)"] = df["Ayuda Total Concedida (€)"].apply(normalizar_numero)

    # Descartar columnas auxiliares
    df = df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore")
    log(f"    → {len(df)} filas")
    return df


def leer_csv(path: Path, log) -> pd.DataFrame:
    log(f"  {path.name}")
    df = None
    for enc in ["utf-8-sig", "latin-1", "cp1252"]:
        try:
            df = pd.read_csv(path, dtype=str, encoding=enc, sep=";")
            if len(df.columns) >= 2:
                break
            df = pd.read_csv(path, dtype=str, encoding=enc, sep=None, engine="python")
            if len(df.columns) >= 2:
                break
        except Exception:
            continue
    if df is None or len(df.columns) < 2:
        log(f"    ERROR: no se pudo leer")
        return pd.DataFrame()

    df.columns = [normalizar(c) for c in df.columns]
    mapa = dict(MAPA_CSV)
    for c in df.columns:
        if "conced" in c:
            mapa[c] = "Ayuda Total Concedida (€)"
    df = df.rename(columns={c: mapa[c] for c in df.columns if c in mapa})

    # Detección de emergencia para columna Título
    if "Título" not in df.columns:
        for c in df.columns:
            cn = normalizar(c)
            if "titulo" in cn or "denominacion" in cn:
                df = df.rename(columns={c: "Título"})
                log(f"    (columna '{c}' → 'Título' por similitud)")
                break

    if "Área / Subárea" in df.columns and "_subarea" in df.columns:
        df["Área / Subárea"] = df["Área / Subárea"].fillna("") + df["_subarea"].apply(
            lambda s: " / " + s if pd.notna(s) and s else ""
        )

    df["Fuente"] = "ANUALES"
    for col in ["Referencia Padre", "Rol (Solicitante/Participante)", "Centro",
                "Tipo de Centro", "Subtipo de Centro", "Sector Público"]:
        if col not in df.columns:
            df[col] = ""
    df["Prioridad Temática / Reto / Área"] = df.get("Área / Subárea", "")

    for col in ["Título", "Resumen"]:
        if col in df.columns:
            df[col] = df[col].apply(limpiar)
    if "Ayuda Total Concedida (€)" in df.columns:
        df["Ayuda Total Concedida (€)"] = df["Ayuda Total Concedida (€)"].apply(normalizar_numero)

    df = df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore")
    log(f"    → {len(df)} filas")
    return df


# --------------------------------------------------------------
# Construcción de la BD
# --------------------------------------------------------------

DDL_PROYECTOS = """
CREATE TABLE IF NOT EXISTS proyectos (
    id                          INTEGER PRIMARY KEY,
    fuente                      TEXT,
    ano_convocatoria            INTEGER,
    convocatoria_programa       TEXT,
    referencia_padre            TEXT,
    referencia                  TEXT,
    titulo                      TEXT,
    resumen                     TEXT,
    palabras_clave              TEXT,
    prioridad_tematica          TEXT,
    area_subarea                TEXT,
    organismo                   TEXT,
    nif_cif                     TEXT,
    rol                         TEXT,
    centro                      TEXT,
    tipo_centro                 TEXT,
    subtipo_centro              TEXT,
    comunidad_autonoma          TEXT,
    provincia                   TEXT,
    sector_publico              TEXT,
    genero                      TEXT,
    ayuda_total                 REAL,
    texto_norm                  TEXT
);
"""
# texto_norm = normalizar(titulo + resumen + palabras_clave)
# Permite búsqueda con LIKE puro (sin función Python en SQLite → muy rápido).

DDL_FTS = ""  # FTS5 retirado: texto_norm + LIKE es más rápido y correcto para español
DDL_TRIGGER_INSERT = ""

# Columna canonical → nombre de columna en BD
COL_MAP = {
    "Fuente":                          "fuente",
    "Año Convocatoria":                "ano_convocatoria",
    "Convocatoria / Programa":         "convocatoria_programa",
    "Referencia Padre":                "referencia_padre",
    "Referencia":                      "referencia",
    "Título":                          "titulo",
    "Resumen":                         "resumen",
    "Palabras Clave":                  "palabras_clave",
    "Prioridad Temática / Reto / Área":"prioridad_tematica",
    "Área / Subárea":                  "area_subarea",
    "Organismo / Entidad":             "organismo",
    "NIF / CIF":                       "nif_cif",
    "Rol (Solicitante/Participante)":  "rol",
    "Centro":                          "centro",
    "Tipo de Centro":                  "tipo_centro",
    "Subtipo de Centro":               "subtipo_centro",
    "Comunidad Autónoma":              "comunidad_autonoma",
    "Provincia":                       "provincia",
    "Sector Público":                  "sector_publico",
    "Género":                          "genero",
    "Ayuda Total Concedida (€)":       "ayuda_total",
}


def df_to_rows(df: pd.DataFrame) -> list[tuple]:
    """Convierte un DataFrame a lista de tuplas para insertar en proyectos."""
    cols_bd = list(COL_MAP.values())
    rows = []
    for _, row in df.iterrows():
        vals = []
        for canon, bd_col in COL_MAP.items():
            val = row.get(canon, None)
            if bd_col == "ano_convocatoria":
                try:
                    val = int(float(val)) if val not in (None, "", "nan") else None
                except (ValueError, TypeError):
                    val = None
            elif bd_col == "ayuda_total":
                try:
                    val = float(val) if val not in (None, "", "nan") else None
                except (ValueError, TypeError):
                    val = None
            else:
                val = str(val).strip() if val is not None and str(val) != "nan" else ""
            vals.append(val)
        # texto_norm: concatenación normalizada para búsqueda LIKE rápida
        titulo_n    = normalizar(str(row.get("Título",         "") or ""))
        resumen_n   = normalizar(str(row.get("Resumen",        "") or ""))
        pk_n        = normalizar(str(row.get("Palabras Clave", "") or ""))
        vals.append(f"{titulo_n} {resumen_n} {pk_n}")
        rows.append(tuple(vals))
    return rows


def build(dir_fuentes: Path, log):
    dir_rtc     = dir_fuentes / "RTC-CPP-PLE"
    dir_anuales = dir_fuentes / "ANUALES"

    for d, nombre in [(dir_rtc, "RTC-CPP-PLE"), (dir_anuales, "ANUALES")]:
        if not d.exists():
            log(f"ERROR: no se encontró {d}")
            sys.exit(1)

    # --Leer RTC-CPP-PLE --
    log("\n--RTC-CPP-PLE --------------------------")
    frames_rtc = []
    for p in sorted(dir_rtc.glob("*.xlsx")):
        df = leer_excel(p, log)
        if not df.empty:
            frames_rtc.append(df)

    rtc = pd.concat(frames_rtc, ignore_index=True) if frames_rtc else pd.DataFrame()
    refs_rtc = set(rtc["Referencia"].dropna()) if "Referencia" in rtc.columns else set()
    log(f"  RTC total: {len(rtc)} filas | {len(refs_rtc)} referencias únicas")

    # --Leer ANUALES --
    log("\n--ANUALES ------------------------------")
    frames_csv = []
    for p in sorted(dir_anuales.glob("*.csv")):
        df = leer_csv(p, log)
        if not df.empty:
            if refs_rtc and "Referencia" in df.columns:
                antes = len(df)
                df = df[~df["Referencia"].isin(refs_rtc)]
                desc = antes - len(df)
                if desc:
                    log(f"    ({desc} duplicados RTC descartados)")
            frames_csv.append(df)

    anuales = pd.concat(frames_csv, ignore_index=True) if frames_csv else pd.DataFrame()
    log(f"  ANUALES total (sin duplicados RTC): {len(anuales)} filas")

    # --Combinar y deduplicar --
    log("\n--Combinando ---------------------------")
    todos = pd.concat([rtc, anuales], ignore_index=True)
    antes = len(todos)
    if "Referencia" in todos.columns:
        todos = todos.drop_duplicates(subset=["Referencia"], keep="first")
    log(f"  Total final: {len(todos)} filas ({antes - len(todos)} duplicados adicionales)")

    # --Asegurar todas las columnas canónicas --
    for col in COLS_BD:
        if col not in todos.columns:
            todos[col] = ""

    # --Escribir BD --
    log(f"\n--Escribiendo {DB_PATH} ----------------")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(DDL_PROYECTOS)

        cols_bd = list(COL_MAP.values()) + ["texto_norm"]
        placeholders = ", ".join("?" * len(cols_bd))
        sql_insert = f"INSERT INTO proyectos ({', '.join(cols_bd)}) VALUES ({placeholders})"

        rows = df_to_rows(todos)
        con.executemany(sql_insert, rows)
        con.commit()
        log(f"  {len(rows)} filas insertadas")

        # Tamaño del fichero
        size_mb = DB_PATH.stat().st_size / 1_048_576
        log(f"  Tamaño: {size_mb:.1f} MB")
    finally:
        con.close()

    log("\n✓ BD generada correctamente")


# --------------------------------------------------------------
# Punto de entrada
# --------------------------------------------------------------

def main():
    # Ruta por defecto: misma ubicación que el repo (OneDrive de Lourdes)
    default_fuentes = (
        Path.home()
        / "OneDrive - MINISTERIO DE CIENCIA E INNOVACIÓN"
        / "General - Unidad de Apoyo"
        / "08-PROYECTOS"
        / "01-BUSQUEDA DE PROYECTOS"
        / "FUENTES_DE_DATOS"
    )

    parser = argparse.ArgumentParser(description="Genera data/proyectos.db desde FUENTES_DE_DATOS/")
    parser.add_argument(
        "--fuentes",
        type=Path,
        default=default_fuentes,
        help=f"Ruta a FUENTES_DE_DATOS/ (defecto: {default_fuentes})",
    )
    args = parser.parse_args()

    def log(msg):
        print(msg, flush=True)

    log(f"Fuentes: {args.fuentes}")
    build(args.fuentes, log)


if __name__ == "__main__":
    main()
