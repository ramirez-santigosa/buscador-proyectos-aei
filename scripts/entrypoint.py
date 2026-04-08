"""
Entrypoint para Hugging Face Spaces (y cualquier despliegue Docker).

Lanza uvicorn usando data/proyectos.db que debe estar presente en el contenedor.
El fichero se incluye en la imagen vía el repositorio del Space (pestaña Files en HF).
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import os

DB_PATH = _ROOT / "data" / "proyectos.db"
HOST    = os.getenv("HOST", "0.0.0.0")
PORT    = int(os.getenv("PORT", "7860"))


def main():
    print("[entrypoint] Buscador de Proyectos AEI — arrancando")
    print(f"[entrypoint] Buscando BD en: {DB_PATH}")

    if not DB_PATH.exists():
        print("[entrypoint] ERROR: data/proyectos.db no encontrada.")
        print("[entrypoint] Sube el fichero al Space desde la pestaña Files de HF.")
        sys.exit(1)

    size_mb = DB_PATH.stat().st_size / 1_048_576
    if size_mb < 1:
        print(f"[entrypoint] ERROR: data/proyectos.db parece un puntero LFS ({size_mb:.3f} MB).")
        print("[entrypoint] En HF Space → Files → proyectos.db → verifica que sea el fichero real.")
        sys.exit(1)

    print(f"[entrypoint] BD encontrada ({size_mb:.1f} MB)")
    print(f"[entrypoint] Iniciando uvicorn en {HOST}:{PORT}")

    import uvicorn
    uvicorn.run("api.main:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
