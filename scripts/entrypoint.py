"""
Entrypoint para Hugging Face Spaces (y cualquier despliegue Docker).

1. Si data/proyectos.db no existe, la descarga de GitHub Releases.
2. Lanza uvicorn en 0.0.0.0:7860.

Variable de entorno:
  DB_RELEASE_URL  — URL completa del asset (opcional; si no se define
                    se usa el latest release de GitHub)
"""

import os
import sys
import urllib.request
from pathlib import Path

# Asegurar que el root del repo esté en el path (necesario cuando se ejecuta
# como `python scripts/entrypoint.py` desde cualquier directorio)
_HERE   = Path(__file__).resolve().parent
_ROOT   = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DB_PATH = _ROOT / "data" / "proyectos.db"

GITHUB_REPO    = "ramirez-santigosa/buscador-proyectos-aei"
DB_ASSET_NAME  = "proyectos.db"
DB_RELEASE_URL = os.getenv(
    "DB_RELEASE_URL",
    f"https://github.com/{GITHUB_REPO}/releases/latest/download/{DB_ASSET_NAME}",
)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7860"))


# ── Descarga con barra de progreso ────────────────────────────────────────

def _progreso(count, block_size, total_size):
    descargado = count * block_size
    if total_size > 0:
        pct = min(descargado * 100 / total_size, 100)
        mb  = descargado / 1_048_576
        print(f"\r  {pct:5.1f}%  ({mb:.0f} MB)", end="", flush=True)


def descargar_db():
    print(f"[entrypoint] Descargando BD desde:\n  {DB_RELEASE_URL}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB_PATH.with_suffix(".tmp")
    try:
        urllib.request.urlretrieve(DB_RELEASE_URL, tmp, reporthook=_progreso)
        print()  # nueva línea tras el progreso
        tmp.rename(DB_PATH)
        size_mb = DB_PATH.stat().st_size / 1_048_576
        print(f"[entrypoint] BD descargada correctamente ({size_mb:.1f} MB)")
    except Exception as exc:
        if tmp.exists():
            tmp.unlink()
        print(f"\n[entrypoint] ERROR al descargar la BD: {exc}")
        print("[entrypoint] Opciones:")
        print("  1. Genera la BD localmente con:  python scripts/build_db.py")
        print("  2. Define DB_RELEASE_URL con la URL correcta del asset.")
        sys.exit(1)


# ── Punto de entrada ──────────────────────────────────────────────────────

def main():
    print(f"[entrypoint] Buscador de Proyectos AEI — arrancando")

    if DB_PATH.exists():
        size_mb = DB_PATH.stat().st_size / 1_048_576
        print(f"[entrypoint] BD encontrada ({size_mb:.1f} MB) — no es necesario descargar")
    else:
        descargar_db()

    print(f"[entrypoint] Iniciando uvicorn en {HOST}:{PORT}")
    import uvicorn
    uvicorn.run("api.main:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
