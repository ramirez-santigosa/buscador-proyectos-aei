"""
FastAPI — Buscador de Proyectos AEI
Endpoints:
  POST /buscar        → resumen JSON (estadísticas + desglose por término)
  POST /descargar-xlsx → devuelve el Excel como descarga
  POST /descargar-pdf  → devuelve el PDF como descarga
  GET  /health        → estado de la API
"""

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


@app.post("/buscar", response_model=ResumenBusqueda)
def buscar_endpoint(req: BusquedaRequest):
    result = buscar(
        keywords=req.keywords,
        and_terms=req.and_terms or None,
        db_path=DB_PATH,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="No se encontraron proyectos.")

    anos = [c for c in result.df_terminos_proyectos.columns if c not in ("Término",)]

    return ResumenBusqueda(
        n_proyectos=result.n_proyectos,
        ayuda_total=result.ayuda_total,
        keywords=result.keywords,
        and_terms=result.and_terms,
        anos=anos,
        terminos_proyectos=result.df_terminos_proyectos.to_dict(orient="records"),
        terminos_ayuda=result.df_terminos_ayuda.to_dict(orient="records"),
    )


@app.post("/descargar-xlsx")
def descargar_xlsx(req: BusquedaRequest):
    from core.export_xlsx import generar_xlsx

    result = buscar(keywords=req.keywords, and_terms=req.and_terms or None, db_path=DB_PATH)
    if result is None:
        raise HTTPException(status_code=404, detail="No se encontraron proyectos.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    terminos_fn = "_".join(k.replace(" ", "-")[:15] for k in req.keywords[:3])
    nombre = f"AEI_2018_{stamp}_{terminos_fn}.xlsx"

    tmp = Path(tempfile.gettempdir()) / nombre
    generar_xlsx(result, tmp)

    return FileResponse(
        path=str(tmp),
        filename=nombre,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/descargar-pdf")
def descargar_pdf(req: BusquedaRequest):
    from core.export_pdf import generar_pdf

    result = buscar(keywords=req.keywords, and_terms=req.and_terms or None, db_path=DB_PATH)
    if result is None:
        raise HTTPException(status_code=404, detail="No se encontraron proyectos.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    terminos_fn = "_".join(k.replace(" ", "-")[:15] for k in req.keywords[:3])
    nombre = f"AEI_2018_{stamp}_{terminos_fn}.pdf"

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
