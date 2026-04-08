# Buscador de Proyectos AEI

Herramienta web para buscar proyectos de I+D+i financiados por la Agencia Estatal de Investigación (AEI) desde 2018.

## Arquitectura

```
Frontend (HTML+JS vanilla)  ──HTTP/JSON──►  Backend FastAPI (Python)
                                                    │
                                                    ├── SQLite + FTS5 (data/proyectos.db)
                                                    └── openpyxl / matplotlib / WeasyPrint
```

## Estructura

```
buscador-proyectos-aei/
├── api/           ← FastAPI: endpoints REST
├── core/          ← lógica de negocio (búsqueda, exportación, mapas)
├── web/           ← frontend HTML/JS vanilla (portable a Drupal)
├── scripts/       ← herramientas de mantenimiento (build_db.py)
├── data/          ← proyectos.db (generado con scripts/build_db.py)
├── drupal/        ← plantilla módulo Drupal (D9/D10)
├── Dockerfile     ← despliegue en Hugging Face Spaces
└── requirements.txt
```

## Puesta en marcha (desarrollo local)

```bash
# 1. Crear y activar entorno virtual
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate     # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Generar la base de datos (requiere acceso a FUENTES_DE_DATOS/)
python scripts/build_db.py

# 4. Arrancar la API
uvicorn api.main:app --reload
```

El frontend se sirve en `http://localhost:8000`.

## Actualización de datos

```bash
python scripts/build_db.py
```

El script lee `FUENTES_DE_DATOS/ANUALES/*.csv` y `FUENTES_DE_DATOS/RTC-CPP-PLE/*.xlsx`,
deduplica (RTC tiene prioridad sobre ANUALES) y regenera `data/proyectos.db`.
Después hacer commit del `.db` actualizado.

## Despliegue

El repo incluye un `Dockerfile` listo para Hugging Face Spaces (Docker SDK).
El frontend y la API se sirven desde la misma URL.
