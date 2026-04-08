# TODO (Bloque 6): Dockerfile para Hugging Face Spaces (Docker SDK)
# Base imagen Python + dependencias de WeasyPrint (GTK nativo en Linux)
FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para WeasyPrint y geopandas
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces expone el puerto 7860
EXPOSE 7860

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
