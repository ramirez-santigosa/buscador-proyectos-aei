# Briefing — Buscador de Proyectos AEI (versión web)

> Documento de continuidad para retomar el trabajo en una nueva sesión con Claude Code.
> Última actualización: **2026-04-08**.

---

## Qué es este proyecto

Migración de la herramienta de escritorio **Buscador de Proyectos AEI**
(`Buscador_Proyectos.exe`, Tkinter + win32com + xlsxwriter, 1.277 líneas)
a una **aplicación web** accesible sin instalación, desplegada en Hugging Face Spaces
y preparada para integrarse en la web institucional de la AEI (Drupal 9.5.11).

Busca proyectos de I+D+i financiados por la AEI desde 2018 por palabras clave,
con filtros opcionales por CIF/NIF y convocatoria, y genera estadísticas,
gráfico, mapa coroplético de CCAA, Excel (3 hojas) y PDF.

---

## Estado actual: APLICACIÓN FUNCIONAL Y DESPLEGADA

| Componente | Estado |
|---|---|
| Backend FastAPI + SQLite | ✅ Completo |
| Frontend HTML/JS vanilla | ✅ Completo |
| Excel (3 hojas) con logo, gráfico y mapa | ✅ Completo |
| PDF con WeasyPrint (Linux/Docker) | ✅ Completo |
| Mapa coroplético CCAA | ✅ Completo |
| Filtro por CIF/NIF | ✅ Completo |
| Filtro por convocatoria | ✅ Completo |
| Marca 2025* (convocatorias pendientes) | ✅ Completo |
| Despliegue en Hugging Face Spaces | ✅ Activo |
| Base de datos (142 MB) en HF LFS | ✅ Configurado |

---

## Dos ubicaciones del proyecto

### 1. Repositorio de desarrollo — Git (GitHub + HF Spaces)

```
C:\Users\lourdes.ramirez\Code\buscador-proyectos-aei\
```

- Es el **directorio de trabajo principal**.
- Repositorio Git con dos remotos configurados:
  - **GitHub** (código fuente): `https://github.com/ramirez-santigosa/buscador-proyectos-aei`
  - **HF Spaces** (despliegue): `https://huggingface.co/spaces/malorasa/BuscadorProyectos`
- Cualquier cambio se publica con:
  ```bash
  git add <ficheros>
  git commit -m "descripción"
  git push origin main   # → GitHub
  git push space main    # → Hugging Face (lanza rebuild automático)
  ```
- La base de datos `data/proyectos.db` (142 MB) **no está en Git**
  (está en `.gitignore`). En HF Spaces se sube directamente como fichero LFS.
  El contenedor la descarga en tiempo de ejecución si no está presente.

### 2. Proyecto original — OneDrive (solo referencia)

```
C:\Users\lourdes.ramirez\OneDrive - MINISTERIO DE CIENCIA E INNOVACIÓN\
  General - Unidad de Apoyo\08-PROYECTOS\01-BUSQUEDA DE PROYECTOS\
```

- Contiene el `.exe` original, los datos fuente (`FUENTES_DE_DATOS/`) y este briefing.
- **Solo lectura para el proyecto web** — no se edita ni se hace commit desde aquí.
- Los CSVs y Excels de `FUENTES_DE_DATOS/` se usan con `scripts/build_db.py`
  para regenerar `proyectos.db` cuando hay nuevas convocatorias.

---

## Arquitectura

```
Usuario (navegador)
    │ fetch JSON / blob
    ▼
web/index.html + app.js + style.css   ← frontend vanilla (sin framework)
    │ servido como StaticFiles por FastAPI
    ▼
api/main.py (FastAPI)
    ├── POST /buscar          → JSON con estadísticas + desglose
    ├── POST /descargar-xlsx  → fichero .xlsx
    └── POST /descargar-pdf   → fichero .pdf (solo Linux/Docker)
    │
    ├── core/search.py        ← lógica de búsqueda y agregaciones
    ├── core/db.py            ← consultas SQLite (FTS5 + LIKE)
    ├── core/export_xlsx.py   ← Excel 3 hojas (xlsxwriter)
    ├── core/export_pdf.py    ← PDF (WeasyPrint, HTML→PDF)
    └── core/maps.py          ← mapa CCAA (geopandas + matplotlib)
    │
data/proyectos.db             ← SQLite 142 MB (no en Git, en HF LFS)
```

El frontend puede moverse a Drupal cambiando la constante `API_BASE_URL`
en `web/app.js` a la URL del servidor de la API.

---

## Estructura del repositorio

```
buscador-proyectos-aei/
├── api/
│   ├── main.py            FastAPI: endpoints, CORS, servir estático
│   └── schemas.py         Pydantic: BusquedaRequest, ResumenBusqueda
├── core/
│   ├── text.py            normalizar(), COLS_SALIDA
│   ├── db.py              buscar_proyectos() sobre SQLite
│   ├── search.py          buscar() → BusquedaResult (dataclass)
│   ├── export_xlsx.py     generar_xlsx() — 3 hojas, logo, gráfico, mapa
│   ├── export_pdf.py      generar_pdf() — WeasyPrint HTML→PDF
│   └── maps.py            generar_mapa_ccaa() — geopandas + matplotlib
├── web/
│   ├── index.html         UI: formulario + resultados
│   ├── app.js             fetch, renderizado tablas/gráfico
│   ├── style.css          estilos AEI (scope .buscador-aei)
│   └── logo_aei.png       logo (1755×1234 px, 150 DPI)
├── scripts/
│   ├── build_db.py        ingesta CSV/Excel → proyectos.db
│   └── entrypoint.py      descarga proyectos.db en HF si no existe
├── data/
│   ├── proyectos.db       ← NO en Git (142 MB, en .gitignore)
│   └── ccaa.geojson       geometrías CCAA para el mapa
├── Dockerfile             imagen Docker para HF Spaces
├── requirements.txt
├── BRIEFING.md            este documento
└── .gitignore
```

---

## Base de datos (proyectos.db)

- **Tamaño:** 142 MB — excluida del repositorio Git.
- **Dónde está en producción:** subida directamente a HF Spaces como fichero LFS
  (`https://huggingface.co/spaces/malorasa/BuscadorProyectos`).
- **Cómo se regenera localmente:**
  ```bash
  cd C:\Users\lourdes.ramirez\Code\buscador-proyectos-aei
  python scripts/build_db.py
  ```
  Lee `FUENTES_DE_DATOS/` de OneDrive (ruta hardcodeada en `build_db.py`).
- **Cómo subirla a HF Spaces** (cuando hay datos nuevos):
  ```bash
  # En el repo de HF Spaces (git lfs track "*.db" ya configurado)
  git -C <ruta-repo-hf> add data/proyectos.db
  git -C <ruta-repo-hf> commit -m "Actualiza proyectos.db"
  git -C <ruta-repo-hf> push space main
  ```
  O subirla manualmente desde la interfaz web de HF Spaces.

---

## Cómo retomar el desarrollo

### Inicio de sesión con Claude Code

1. Abrir terminal en `C:\Users\lourdes.ramirez\Code\buscador-proyectos-aei\`
2. Lanzar Claude Code (CLI o extensión VS Code)
3. Decirle a Claude: *"Lee el BRIEFING.md y retomamos donde lo dejamos"*

### Comandos habituales

```bash
# Arrancar el servidor en local (para probar antes de subir)
cd C:\Users\lourdes.ramirez\Code\buscador-proyectos-aei
uvicorn api.main:app --reload

# Ver estado del repo
git status
git log --oneline -10

# Publicar cambios
git add <ficheros_modificados>
git commit -m "descripción del cambio"
git push origin main    # GitHub
git push space main     # Hugging Face → rebuild automático (~2 min)

# Comprobar que ambos remotos están bien
git remote -v
# origin  https://github.com/ramirez-santigosa/buscador-proyectos-aei.git
# space   https://huggingface.co/spaces/malorasa/BuscadorProyectos
```

### Notas operativas

- **PDF en local (Windows):** WeasyPrint requiere GTK Runtime. Sin él el endpoint
  `/descargar-pdf` devuelve 503. En HF Spaces (Linux/Docker) funciona sin problema.
- **Zona horaria de nombres de fichero:** el servidor usa `Europe/Madrid`
  (hora oficial española, CEST/CET). Implementado con `zoneinfo.ZoneInfo`.
- **Logo en Excel:** 1755×1234 px a **150 DPI**. La escala se calcula dinámicamente
  en `export_xlsx.py` para que ocupe exactamente las 3 filas de cabecera:
  `scale = (total_px - y_offset) / int(1234 * 96/150)`.
- **Convocatoria 2025:** marcada con `*` en todos los outputs
  ("* 2025: Convocatorias pendientes de resolver").
- **Filtro de convocatoria:** se aplica en Python (no en SQL) porque SQLite `lower()`
  no gestiona tildes en español. Usa `core.text.normalizar()`.

---

## Decisiones de diseño clave

| Decisión | Por qué |
|---|---|
| Vanilla JS (sin React/Vue) | Portable a Drupal sin build step |
| CSS bajo `.buscador-aei` | No contamina el tema de Drupal |
| SQLite (no MySQL) | Sin servidor, sin coste, datos solo lectura |
| WeasyPrint (no win32com) | Funciona en Linux/Docker |
| xlsxwriter (no openpyxl) | Formato más rico, más rápido |
| HF Spaces Docker | Gratis, sin sleep, geopandas funciona |
| `API_BASE_URL = ""` | Mismo origen en HF, configurable para Drupal |
| proyectos.db fuera de Git | 142 MB supera límite de GitHub (100 MB) |

---

## URLs activas

| Recurso | URL |
|---|---|
| Aplicación en producción | `https://malorasa-buscadoproyectos.hf.space` |
| Repositorio GitHub | `https://github.com/ramirez-santigosa/buscador-proyectos-aei` |
| HF Spaces (repo+deploy) | `https://huggingface.co/spaces/malorasa/BuscadorProyectos` |
| API health check | `https://malorasa-buscadoproyectos.hf.space/health` |
| API docs (Swagger) | `https://malorasa-buscadoproyectos.hf.space/docs` |

---

## Pendiente / posibles mejoras futuras

- Integración en Drupal 9/10 como bloque (módulo `drupal/` en el repo, aún vacío)
- Paginación del listado completo en la web (ahora se muestran estadísticas, no filas)
- Actualización de datos: automatizar `build_db.py` + subida a HF con GitHub Actions
- Tests de paridad con el `.exe` original
- Campo de búsqueda por año de convocatoria
