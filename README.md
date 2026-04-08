---
title: Buscador de Proyectos AEI
emoji: 🔬
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

# Buscador de Proyectos AEI

Herramienta web para buscar proyectos de I+D+i financiados por la Agencia Estatal de Investigación (AEI) desde 2018.

## Arquitectura

```
Frontend (HTML+JS vanilla)  ──HTTP/JSON──►  Backend FastAPI (Python)
                                                    │
                                                    ├── SQLite (data/proyectos.db, ~245 MB)
                                                    └── openpyxl / matplotlib / WeasyPrint
```

## Estructura del repositorio

```
buscador-proyectos-aei/
├── api/           ← FastAPI: endpoints REST
├── core/          ← lógica de negocio (búsqueda, exportación, mapas)
├── web/           ← frontend HTML/JS vanilla (portable a Drupal)
├── scripts/       ← herramientas de mantenimiento
│   ├── build_db.py    ← genera data/proyectos.db desde FUENTES_DE_DATOS/
│   ├── upload_db.py   ← sube proyectos.db a GitHub Releases
│   └── entrypoint.py  ← arranque Docker: descarga BD + lanza uvicorn
├── data/
│   └── ccaa.geojson   ← geometrías de CCAA (derivado del shapefile IGN)
├── drupal/        ← plantilla módulo Drupal D9/D10
├── Dockerfile
└── requirements.txt
```

---

## Puesta en marcha — desarrollo local

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
# → http://localhost:8000
```

> **PDF en Windows:** WeasyPrint requiere GTK. La generación de PDF
> solo funciona plenamente dentro del contenedor Docker (Linux).

---

## Actualización de datos

Cuando lleguen nuevos CSV/Excel al directorio `FUENTES_DE_DATOS/`:

```bash
# 1. Regenerar la BD
python scripts/build_db.py

# 2. Subir la nueva BD a GitHub Releases
python scripts/upload_db.py --token ghp_TU_TOKEN

# 3. En HF Spaces, reiniciar el Space (o esperar al redeploy automático)
```

---

## Despliegue en Hugging Face Spaces

### Primera vez

1. **Crear un release en GitHub** con la BD inicial:
   ```bash
   python scripts/upload_db.py --token ghp_TU_TOKEN --tag data-latest
   ```

2. **Crear el Space** en [huggingface.co/new-space](https://huggingface.co/new-space):
   - SDK: **Docker**
   - Visibilidad: Public

3. **Conectar el repositorio GitHub** (o hacer push al repo del Space).

4. El Space arranca automáticamente:
   - Descarga `proyectos.db` desde GitHub Releases
   - Lanza la API en el puerto 7860
   - Sirve el frontend en la URL del Space

### Variable de entorno opcional

| Variable | Descripción | Defecto |
|---|---|---|
| `DB_RELEASE_URL` | URL directa al asset `.db` | `github.com/.../releases/latest/download/proyectos.db` |

Se configura en **HF Spaces → Settings → Repository secrets**.

---

## Integración en Drupal

El frontend está en `web/` y usa:
- **Sin frameworks JS** (vanilla, sin build step)
- **CSS scopeado** bajo `.buscador-aei`
- **`API_BASE_URL`** configurable en `app.js` (cambiar a la URL del backend)

Para integrar en Drupal 9/10: ver `drupal/README.md`.
