"""
FastAPI — Buscador de Proyectos AEI
Endpoints:
  POST /buscar        → resumen JSON (estadísticas + desglose por término)
  POST /descargar-xlsx → devuelve el Excel como descarga
  POST /descargar-pdf  → devuelve el PDF como descarga
  GET  /health        → estado de la API
"""

import base64
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.schemas import BusquedaRequest, ResumenBusqueda
from core.search import buscar

# ── Configuración ─────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parents[1]
WEB_DIR = REPO / "web"
DATA_DIR = REPO / "data"
DB_PATH = DATA_DIR / "proyectos.db"

app = FastAPI(
    title="Buscador de Proyectos AEI",
    description="API para buscar proyectos de I+D+i financiados por la AEI desde 2018.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restringir en producción si se desea
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["content-disposition"],  # necesario para que el browser lea el nombre del fichero
)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    db_ok = DB_PATH.exists()
    return {
        "status": "ok" if db_ok else "sin_bd",
        "db": str(DB_PATH) if db_ok else "no encontrada",
        "db_size_mb": round(DB_PATH.stat().st_size / 1_048_576, 1) if db_ok else None,
    }


def _df_records(df):
    """Convierte DataFrame a lista de dicts (maneja NaN/inf y tipos numpy)."""
    return json.loads(df.to_json(orient="records", default_handler=str))


def _nombre_fichero(keywords, ext):
    """Genera el nombre de fichero: AEI_desde2018_<primer_termino>_<fecha>."""
    primer = re.sub(r"[^\w\-]", "", keywords[0].replace(" ", "-"))[:25]
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"AEI_desde2018_{primer}_{stamp}.{ext}"


@app.post("/buscar", response_model=ResumenBusqueda)
def buscar_endpoint(req: BusquedaRequest):
    result = buscar(
        keywords=req.keywords,
        and_terms=req.and_terms or None,
        db_path=DB_PATH,
        cif_filter=req.cif_filter or None,
        conv_filter=req.conv_filter or None,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="No se encontraron proyectos.")

    anos = [c for c in result.df_terminos_proyectos.columns if c not in ("Término",)]

    # Mapa coroplético como base64 PNG (falla silenciosamente si no hay geopandas)
    mapa_b64 = ""
    try:
        from core.maps import generar_mapa_ccaa
        terminos_str = " | ".join(req.keywords)
        if req.and_terms:
            terminos_str += "  AND: " + " + ".join(req.and_terms)
        tmp_map = Path(tempfile.gettempdir()) / "mapa_web_tmp.png"
        if generar_mapa_ccaa(result.todas_ccaa, tmp_map, terminos_str, dpi=150):
            mapa_b64 = base64.b64encode(tmp_map.read_bytes()).decode()
            tmp_map.unlink(missing_ok=True)
    except Exception:
        pass

    return ResumenBusqueda(
        n_proyectos=result.n_proyectos,
        ayuda_total=result.ayuda_total,
        keywords=result.keywords,
        and_terms=result.and_terms,
        anos=anos,
        terminos_proyectos=result.df_terminos_proyectos.to_dict(orient="records"),
        terminos_ayuda=result.df_terminos_ayuda.to_dict(orient="records"),
        totales=_df_records(result.totales),
        top_conv=_df_records(result.top_conv),
        top_entidades=_df_records(result.top_entidades),
        top_ccaa=_df_records(result.top_ccaa),
        mapa_b64=mapa_b64,
    )


@app.post("/descargar-xlsx")
def descargar_xlsx(req: BusquedaRequest):
    from core.export_xlsx import generar_xlsx

    result = buscar(keywords=req.keywords, and_terms=req.and_terms or None, db_path=DB_PATH,
                    cif_filter=req.cif_filter or None, conv_filter=req.conv_filter or None)
    if result is None:
        raise HTTPException(status_code=404, detail="No se encontraron proyectos.")

    nombre = _nombre_fichero(req.keywords, "xlsx")
    tmp = Path(tempfile.gettempdir()) / nombre

    try:
        generar_xlsx(result, tmp)
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"Error generando Excel: {e}\n{traceback.format_exc()}")

    return FileResponse(
        path=str(tmp),
        filename=nombre,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/descargar-pdf")
def descargar_pdf(req: BusquedaRequest):
    from core.export_pdf import generar_pdf

    result = buscar(keywords=req.keywords, and_terms=req.and_terms or None, db_path=DB_PATH,
                    cif_filter=req.cif_filter or None, conv_filter=req.conv_filter or None)
    if result is None:
        raise HTTPException(status_code=404, detail="No se encontraron proyectos.")

    nombre = _nombre_fichero(req.keywords, "pdf")

    tmp = Path(tempfile.gettempdir()) / nombre
    pdf = generar_pdf(result, tmp)

    if pdf is None or not tmp.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "La generación de PDF no está disponible en este entorno "
                "(requiere GTK Runtime en Windows). "
                "Funciona automáticamente en el contenedor Docker / HF Spaces."
            ),
        )

    return FileResponse(
        path=str(tmp),
        filename=nombre,
        media_type="application/pdf",
    )


# ── Frontend estático ─────────────────────────────────────────────────────────
# Se sirve en último lugar para no solapar con los endpoints /buscar etc.
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
