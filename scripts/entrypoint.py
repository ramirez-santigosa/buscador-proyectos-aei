"""
Entrypoint para Hugging Face Spaces (y cualquier despliegue Docker).

Si data/proyectos.db no existe (o es un puntero LFS vacío), la descarga
desde DB_URL antes de arrancar uvicorn.

Variable de entorno opcional:
  DB_URL  — URL de descarga directa del fichero .db
            (por defecto apunta al asset LFS del propio Space de HF)
"""

import os
import sys
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DB_PATH = _ROOT / "data" / "proyectos.db"
DB_URL  = os.getenv(
    "DB_URL",
    "https://huggingface.co/spaces/malorasa/BuscadorProyectos/resolve/main/data/proyectos.db",
)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7860"))

MIN_SIZE_MB = 10  # si el fichero pesa menos, es un puntero LFS


def _es_valida():
    if not DB_PATH.exists():
        return False
    return DB_PATH.stat().st_size / 1_048_576 >= MIN_SIZE_MB


def _progreso(count, block_size, total):
    if total > 0:
        pct = min(count * block_size * 100 / total, 100)
        mb  = count * block_size / 1_048_576
        print(f"\r  {pct:5.1f}%  ({mb:.0f} MB descargados)", end="", flush=True)


def descargar():
    print(f"[entrypoint] Descargando BD desde:\n  {DB_URL}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB_PATH.with_suffix(".tmp")
    try:
        urllib.request.urlretrieve(DB_URL, tmp, reporthook=_progreso)
        print()
        tmp.rename(DB_PATH)
        mb = DB_PATH.stat().st_size / 1_048_576
        print(f"[entrypoint] BD descargada ({mb:.1f} MB)")
    except Exception as exc:
        if tmp.exists():
            tmp.unlink()
        print(f"\n[entrypoint] ERROR al descargar: {exc}")
        print("[entrypoint] Comprueba que DB_URL sea accesible y el fichero no sea privado.")
        sys.exit(1)


def main():
    print("[entrypoint] Buscador de Proyectos AEI — arrancando")

    if _es_valida():
        mb = DB_PATH.stat().st_size / 1_048_576
        print(f"[entrypoint] BD encontrada ({mb:.1f} MB)")
    else:
        descargar()

    print(f"[entrypoint] Iniciando uvicorn en {HOST}:{PORT}")
    import uvicorn
    uvicorn.run("api.main:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
