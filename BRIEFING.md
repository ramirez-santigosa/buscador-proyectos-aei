# Briefing — Buscador de Proyectos AEI (versión web)

> Documento de continuidad para retomar el trabajo en una nueva sesión.
> Última actualización: 2026-04-07.

---

## Qué estamos haciendo

Migrar la herramienta de escritorio **Buscador de Proyectos AEI** (Tkinter, distribuida
como `Buscador_Proyectos.exe`) a una **aplicación web** que cualquier persona pueda
usar sin acceso a la carpeta personal de OneDrive de Lourdes, y que sea **fácilmente
trasladable a la web institucional de la AEI (Drupal 9.5.11)** en el futuro.

La herramienta original busca proyectos de I+D+i financiados por la AEI a partir de
palabras clave, consolida dos fuentes (CSVs ANUALES y Excels RTC/CPP/PLE), deduplica,
y genera un Excel + PDF con resultados y estadísticas (incluido un mapa coroplético
de CCAA).

---

## Decisiones tomadas

### 1. Arquitectura: API + frontend desacoplados

```
Frontend (HTML+JS vanilla)  ──HTTP/JSON──►  Backend FastAPI (Python)
                                                    │
                                                    ├── SQLite + FTS5 (data/proyectos.db)
                                                    └── openpyxl / matplotlib / WeasyPrint
```

**Por qué:** el frontend en HTML/JS puro (sin React/Vue, sin build step) se puede
mover a Drupal como bloque/módulo casi tal cual. El backend Python reutiliza el
~70% del código existente.

### 2. Almacenamiento: SQLite con FTS5, versionado en el repo

- Un único fichero `data/proyectos.db` generado por `scripts/build_db.py` desde
  `FUENTES_DE_DATOS/` (que sigue viviendo en OneDrive de Lourdes, no se sube al repo).
- Índice FTS5 sobre Título/Resumen/Palabras Clave → búsqueda casi instantánea.
- Deduplicación RTC>ANUALES hecha en ingesta (no en cada búsqueda).
- Versionado en Git → reproducible, sin servidor, sin coste, sin credenciales.
- **Tamaño esperado:** < 100 MB (FUENTES_DE_DATOS pesa 105 MB en bruto; comprimido
  y deduplicado en SQLite cabrá). Si se pasara, mover a GitHub Releases como asset.
- **Descartado:** MySQL. Para datos públicos, solo lectura, actualizados pocas
  veces al año, con un único administrador, añade coste y fragilidad sin ventaja.

### 3. Hosting backend: Hugging Face Spaces (Docker)

- Gratis, sin sleep, deploy automático desde GitHub.
- Sirve también el frontend estático en la misma URL.
- Alternativas descartadas para fase inicial: Streamlit Cloud (no portable a Drupal),
  Render (sleep), Railway (de pago), Fly.io (requiere tarjeta).

### 4. Generación de PDF: WeasyPrint (HTML → PDF)

- **Problema crítico identificado:** la generación de PDF actual usa
  `win32com.client` (automatiza Excel.exe), que solo funciona en Windows con
  Microsoft Office instalado. **No es portable a Linux / Hugging Face Spaces.**
- **Solución elegida:** WeasyPrint con plantilla HTML/CSS para la hoja
  "Totales anuales".
- **Ventaja extra:** la misma plantilla HTML sirve como vista previa en la web
  y se traslada limpiamente a Drupal como Twig template.
- Alternativas descartadas: LibreOffice headless (+250 MB en imagen Docker),
  ReportLab procedural (menos mantenible).

### 5. Compatibilidad con Drupal

- AEI usa **Drupal 9.5.11** (última de la rama 9.x; 9.x está en EOL desde
  noviembre 2023, pero el módulo se hace **compatible D9 y D10** para que sobreviva
  a una futura migración).
- Reglas de diseño del frontend para integración limpia:
  - **Sin frameworks JS** (vanilla, sin build step)
  - **CSS scopeado** bajo `.buscador-aei` (no contamina el tema de la AEI)
  - **Sin cookies/sesiones** (sin choque con auth de Drupal)
  - **CORS configurable** en la API
  - **`fetch()` con `API_BASE_URL` configurable** (cambiar 1 constante para mover
    el frontend a Drupal)
  - Nombres de campos del formulario alineados con Drupal Webform por si se
    quiere usar ese módulo en el futuro

### 6. "Preguntar dónde guardar el resultado"

Requisito explícito del documento de indicaciones (`SOURCES/INDICACIONES-07.04.26.docx`).
**Se resuelve con `st.download_button` / `<a download>`** → el navegador abre el
diálogo nativo "Guardar como…" del SO. Reemplaza al `filedialog.asksaveasfilename`
de Tkinter actual.

---

## Estructura del repo (objetivo)

```
buscador-proyectos-aei/
├── api/
│   ├── main.py                ← FastAPI: endpoints REST
│   └── schemas.py             ← Pydantic models
├── core/
│   ├── text.py                ← normalizar, limpiar, MAPA_CSV, MAPA_EXCEL
│   ├── db.py                  ← acceso SQLite/FTS5
│   ├── search.py              ← refactor de buscar() leyendo del .db
│   ├── export_xlsx.py         ← generación Excel (xlsxwriter, copia íntegra)
│   ├── export_pdf.py          ← generación PDF (WeasyPrint + HTML)
│   └── maps.py                ← generar_mapa_ccaa (geopandas + matplotlib)
├── web/                       ← FRONTEND (lo que se moverá a Drupal)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── scripts/
│   └── build_db.py            ← ingesta CSV/Excel → proyectos.db (uso local Lourdes)
├── data/
│   ├── proyectos.db           ← BD generada (versionada en Git)
│   └── ccaa.geojson           ← geometrías CCAA (derivado del shapefile IGN)
├── drupal/                    ← plantilla del módulo (no funcional hasta el día D)
│   ├── README.md
│   ├── buscador_aei.info.yml
│   ├── buscador_aei.libraries.yml
│   └── templates/
│       └── block--buscador-aei.html.twig
├── Dockerfile                 ← para HF Spaces
├── requirements.txt
├── README.md
└── BRIEFING.md                ← este documento
```

---

## Estado actual (2026-04-07)

| Item | Estado |
|---|---|
| Lectura de indicaciones del docx | ✅ |
| Análisis de `buscador_proyectos.py` (1.277 líneas) | ✅ |
| Medición de `FUENTES_DE_DATOS/` (105 MB) | ✅ |
| Decisiones de stack | ✅ |
| Repo creado en GitHub | ✅ `https://github.com/ramirez-santigosa/buscador-proyectos-aei` |
| Repo clonado en local | ✅ `C:\Users\lourdes.ramirez\Code\buscador-proyectos-aei` |
| Identidad de git configurada | ⏳ **PENDIENTE** — Lourdes debe ejecutar `git config --global user.name/email` |
| Bloque 1: esqueleto del repo | ⏳ pendiente |
| Bloque 2: ingesta SQLite (`build_db.py`) | ⏳ pendiente |
| Bloque 3: búsqueda + export | ⏳ pendiente |
| Bloque 4: API FastAPI | ⏳ pendiente |
| Bloque 5: frontend HTML/JS | ⏳ pendiente |
| Bloque 6: Dockerfile + despliegue HF Spaces | ⏳ pendiente |
| Bloque 7: plantilla Drupal | ⏳ pendiente |
| Primer commit local | ⏳ pendiente |
| Push a GitHub | ⏳ pendiente (esperar luz verde explícita) |

---

## Mapeo del código existente a la nueva estructura

Análisis del fichero `SOURCES/buscador_proyectos.py` (1.277 líneas).

| Líneas | Bloque | Destino en el nuevo repo |
|---|---|---|
| 1‑270 | Helpers (`normalizar`, `limpiar`, `MAPA_CSV`, `MAPA_EXCEL`, `filtrar_por_keywords`) | `core/text.py` (literal) |
| 169‑261 | `leer_excel`, `leer_csv` | `scripts/build_db.py` (solo se usan en ingesta) |
| 296‑405 | `generar_mapa_ccaa` (geopandas + matplotlib) | `core/maps.py` (literal) |
| 408‑565 | Lógica de búsqueda y agregaciones de `buscar()` | `core/search.py` (refactor: lee de SQLite en vez de CSV/Excel) |
| 566‑920 | Generación Excel `xlsxwriter` (formato muy elaborado) | `core/export_xlsx.py` (literal) |
| 929‑977 | Generación PDF vía `win32com.client` | ⚠️ **REESCRIBIR** → `core/export_pdf.py` con WeasyPrint |
| 984‑1277 | GUI Tkinter (clase `App`) | **DESCARTAR** → `web/index.html` + `app.js` |

---

## Datos clave para la próxima sesión

### Rutas
- **Repo nuevo (donde trabajamos):** `C:\Users\lourdes.ramirez\Code\buscador-proyectos-aei\`
- **Proyecto original (solo lectura para portar código):** `C:\Users\lourdes.ramirez\OneDrive - MINISTERIO DE CIENCIA E INNOVACIÓN\General - Unidad de Apoyo\08-PROYECTOS\01-BUSQUEDA DE PROYECTOS\`
- **Datos fuente (solo lectura, alimentan `build_db.py`):** `...\01-BUSQUEDA DE PROYECTOS\FUENTES_DE_DATOS\`
- **Shapefiles IGN:** `...\01-BUSQUEDA DE PROYECTOS\SOURCES\geodata\SHP_ETRS89\...`

### Tamaños
- `FUENTES_DE_DATOS/ANUALES/` (8 CSVs): **103 MB**
- `FUENTES_DE_DATOS/RTC-CPP-PLE/` (excels): **2.6 MB**
- **Total:** 105 MB → SQLite resultante esperado < 100 MB

### Entorno
- Windows 11, bash (Git Bash) en lugar de PowerShell para la sesión Claude
- Python disponible (el proyecto original tiene un venv en `SOURCES\.venv\` pero el repo nuevo tendrá el suyo propio)
- `git` 2.53 disponible
- `gh` (GitHub CLI) **no** disponible — usar `git` directo
- Repo GitHub: `https://github.com/ramirez-santigosa/buscador-proyectos-aei` (vacío, recién creado)

### Cuestiones abiertas
1. Configuración de identidad de git pendiente (Lourdes la pone antes del primer commit).
2. Dependencias de WeasyPrint en Windows: requiere GTK; en Docker Linux es trivial. Para desarrollo local en Windows quizá haya que instalar GTK runtime, o probar la generación de PDF solo dentro del contenedor.
3. Conversión del shapefile IGN a `ccaa.geojson` ligero (solo geometrías de CCAA): hacerlo durante `build_db.py` o como script aparte.
4. Tests de paridad: comparar el Excel generado por la nueva pipeline con el del `.exe` actual usando los mismos términos de búsqueda. Definir 2‑3 búsquedas patrón.

---

## Próximos pasos inmediatos

Cuando Lourdes retome:

1. **Confirmar** que ha configurado `git config --global user.name/email`.
2. **Empezar Bloque 1+2:**
   - Crear esqueleto de carpetas, `.gitignore`, `requirements.txt` mínimo, `README.md`
   - Implementar `core/text.py` (helpers portados)
   - Implementar `scripts/build_db.py`
   - **Ejecutarlo contra `FUENTES_DE_DATOS/`** y reportar el tamaño real del `.db`
3. Si el `.db` cabe < 100 MB → seguir con Bloque 3.
   Si no → decidir entre optimización (columnas, índices) o GitHub Releases.

---

## Documentos de referencia

- `SOURCES/INDICACIONES-07.04.26.docx` — petición original de Lourdes
- `SOURCES/BRIEFING.md` — briefing del proyecto **original** (descripción detallada de cómo funciona el .exe actual)
- `SOURCES/buscador_proyectos.py` — código fuente original (1.277 líneas, único fichero)
- `SOURCES/manual_buscador.docx` — manual de usuario de la app de escritorio
