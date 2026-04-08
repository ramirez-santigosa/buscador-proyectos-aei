# ── Buscador de Proyectos AEI ── Hugging Face Spaces (Docker SDK) ──────────
#
# La BD (data/proyectos.db, ~245 MB) NO está en la imagen:
# scripts/entrypoint.py la descarga de GitHub Releases al primer arranque.
#
# Variables de entorno disponibles:
#   DB_RELEASE_URL  URL completa del asset (sobreescribe el valor por defecto)

FROM python:3.11-slim

# ── Dependencias del sistema ──────────────────────────────────────────────
# WeasyPrint necesita Pango/GDK-Pixbuf (GTK, disponible en Linux sin GTK completo)
# geopandas/pyogrio incluye su propio GDAL estático, no se necesita sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-xlib-2.0-0 \
        libfontconfig1 \
        libfreetype6 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Usuario no-root (buena práctica en HF Spaces) ────────────────────────
RUN useradd -m -u 1000 aei
WORKDIR /home/aei/app

# ── Dependencias Python ───────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Código de la aplicación ───────────────────────────────────────────────
COPY --chown=aei:aei . .

# Asegurar que el directorio data existe y tiene los permisos correctos
RUN mkdir -p data && chown -R aei:aei data

USER aei

# ── Puerto ────────────────────────────────────────────────────────────────
EXPOSE 7860

# ── Arranque ──────────────────────────────────────────────────────────────
# entrypoint.py descarga proyectos.db si no existe y luego inicia uvicorn
CMD ["python", "scripts/entrypoint.py"]
