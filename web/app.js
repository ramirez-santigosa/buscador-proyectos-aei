// Cambia esta constante para mover el frontend a Drupal (o a otro dominio).
// Vacío = misma URL de origen (HF Spaces / local).
const API_BASE_URL = "";

// ── Estado de la última búsqueda (para los botones de descarga) ──────────────
let _lastRequest = null;

// ── Log ──────────────────────────────────────────────────────────────────────

function log(msg) {
  const el = document.getElementById("ba-log");
  const ahora = new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  el.textContent += `[${ahora}] ${msg}\n`;
  el.scrollTop = el.scrollHeight;
}

function logLimpiar() {
  document.getElementById("ba-log").textContent = "";
}

// ── Utilidades ───────────────────────────────────────────────────────────────

function parsearTerminos(texto) {
  return texto.split(";").map(t => t.trim()).filter(t => t.length > 0);
}

function formatEuros(n) {
  return new Intl.NumberFormat("es-ES", {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  }).format(n) + " €";
}

function formatMillones(n) {
  return new Intl.NumberFormat("es-ES", {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  }).format((n || 0) / 1_000_000) + " M€";
}

function formatMillonesNum(n) {
  return new Intl.NumberFormat("es-ES", {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  }).format((n || 0) / 1_000_000);
}

function formatInt(n) {
  return new Intl.NumberFormat("es-ES").format(Math.round(n));
}

// ── Acciones principales ─────────────────────────────────────────────────────

async function buscar() {
  const keywords   = parsearTerminos(document.getElementById("or-terms").value);
  const andTerms   = parsearTerminos(document.getElementById("and-terms").value);
  const cifFilter  = document.getElementById("cif-filter").value.trim();
  const convFilter = document.getElementById("conv-filter").value.trim();

  if (keywords.length === 0) {
    mostrarError("Introduce al menos un término de búsqueda.");
    return;
  }

  _lastRequest = { keywords, and_terms: andTerms, cif_filter: cifFilter, conv_filter: convFilter };

  logLimpiar();
  ocultarError();
  ocultarResultado();
  ocultarVacio();
  mostrarProgreso("Buscando en la base de datos…");
  document.getElementById("btn-buscar").disabled = true;

  const andLabel = andTerms.length ? `  AND: ${andTerms.join(" + ")}` : "";
  log(`Búsqueda OR: ${keywords.join(" | ")}${andLabel}`);
  log("Conectando con el servidor…");

  try {
    const resp = await fetch(`${API_BASE_URL}/buscar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(_lastRequest),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Error ${resp.status}`);
    }

    const data = await resp.json();
    log(`Encontrados: ${formatInt(data.n_proyectos)} proyectos`);
    log(`Ayuda total: ${formatMillones(data.ayuda_total)}`);
    log("Búsqueda completada ✓");
    mostrarResultado(data);

  } catch (e) {
    log(`ERROR: ${e.message}`);
    mostrarError(e.message === "Failed to fetch"
      ? "No se pudo conectar con el servidor. ¿Está en marcha la API?"
      : e.message);
  } finally {
    ocultarProgreso();
    document.getElementById("btn-buscar").disabled = false;
  }
}

async function descargar(tipo) {
  if (!_lastRequest) return;

  const endpoint = tipo === "xlsx" ? "/descargar-xlsx" : "/descargar-pdf";
  const btn = event.currentTarget;
  const textoOriginal = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Generando…";

  const tipoLabel = tipo === "xlsx" ? "Excel" : "PDF";
  log(`Generando ${tipoLabel}…`);

  try {
    const resp = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(_lastRequest),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Error ${resp.status}`);
    }

    const blob  = await resp.blob();
    const url   = URL.createObjectURL(blob);
    const a     = document.createElement("a");
    const cd    = resp.headers.get("content-disposition") || "";
    const match = cd.match(/filename="?([^";]+)"?/);
    a.href      = url;
    a.download  = match ? match[1] : `resultado.${tipo}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    log(`${tipoLabel} descargado ✓`);

  } catch (e) {
    log(`Aviso al generar ${tipoLabel}: ${e.message}`);
    if (tipo !== "pdf") mostrarError(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = textoOriginal;
  }
}

function limpiar() {
  document.getElementById("or-terms").value   = "";
  document.getElementById("and-terms").value  = "";
  document.getElementById("cif-filter").value  = "";
  document.getElementById("conv-filter").value = "";
  if (_chartInstance) { _chartInstance.destroy(); _chartInstance = null; }
  document.getElementById("ba-stats").innerHTML    = "";
  document.getElementById("ba-desglose").innerHTML = "";
  ocultarResultado();
  ocultarError();
  ocultarProgreso();
  mostrarVacio();
  logLimpiar();
  _lastRequest = null;
}

// ── Renderizado de resultados ────────────────────────────────────────────────

function mostrarResultado(data) {
  const andLabel = data.and_terms.length
    ? `  AND: ${data.and_terms.join(" + ")}`
    : "";

  document.getElementById("ba-result-summary").innerHTML =
    `🔍 <strong>${data.keywords.join(" | ")}${andLabel}</strong><br>` +
    `${formatInt(data.n_proyectos)} proyectos &nbsp;·&nbsp; Ayuda total: ${formatMillones(data.ayuda_total)}`;

  document.getElementById("ba-stats").innerHTML    = renderStats(data);
  document.getElementById("ba-desglose").innerHTML = renderDesglose(data);
  document.getElementById("ba-result").hidden = false;

  // El canvas debe existir en el DOM antes de inicializar Chart.js
  if (data.totales && data.totales.length > 0) {
    renderGrafico(data.totales);
  }
}

// ── Estadísticas consolidadas (sin duplicar) ─────────────────────────────────

const COL_LABELS_STATS = {
  "Año": "Año", "Proyectos": "Nº Proy.", "Hombres": "IP Hombre",
  "Mujeres": "IP Mujer", "No aplica": "No aplica",
  "Ayuda_Total": "Ayuda (M€)", "Convocatoria / Programa": "Convocatoria",
  "Entidad": "Entidad", "Comunidad Autónoma": "C.A.",
};
const EURO_COLS_STATS = ["Ayuda_Total"];
const INT_COLS_STATS  = ["Proyectos", "Hombres", "Mujeres", "No aplica"];

let _chartInstance = null;

function renderStats(data) {
  if (!data.totales || data.totales.length === 0) return "";

  const tblAnos = renderStatsTable(data.totales,       "Totales por año",                     "TOTAL");
  const tblConv = renderStatsTable(data.top_conv,      "Totales por convocatoria / programa",  "TOTAL");
  const tblEnt  = renderStatsTable(data.top_entidades, "Top 10 entidades",                    "TOTAL TOP 10");
  const tblCcaa = renderStatsTable(data.top_ccaa,      "Top 10 Comunidades Autónomas",         "TOTAL TOP 10");

  const mapa = data.mapa_b64
    ? `<div class="ba-mapa-wrap"><img src="data:image/png;base64,${data.mapa_b64}" class="ba-mapa-img" alt="Distribución por CCAA"></div>`
    : "";

  return `
    <div class="ba-stats-header">
      ESTADÍSTICAS CONSOLIDADAS
      <span class="ba-stats-nota">(proyectos sin duplicar)</span>
    </div>
    <div class="ba-stats-grid">
      <div>
        ${tblConv}
        ${tblAnos}
        <p class="ba-table-nota">* 2025: Convocatorias pendientes de resolver.</p>
        <canvas id="ba-chart" class="ba-chart-canvas"></canvas>
      </div>
      <div>
        ${tblEnt}
        ${tblCcaa}
        ${mapa}
      </div>
    </div>`;
}

function renderStatsTable(rows, titulo, totalVal) {
  if (!rows || rows.length === 0) return "";
  const cols = Object.keys(rows[0]);
  const firstCol = cols[0];

  const headers = cols.map(c => `<th>${COL_LABELS_STATS[c] || c}</th>`).join("");

  const bodyRows = rows.map(row => {
    const isTotal = String(row[firstCol]) === totalVal;
    const cls = isTotal ? ' class="ba-row-total"' : "";
    const cells = cols.map(c => {
      const v = row[c];
      if (EURO_COLS_STATS.includes(c)) return `<td class="num">${formatMillonesNum(v || 0)}</td>`;
      if (INT_COLS_STATS.includes(c))  return `<td class="num">${formatInt(v || 0)}</td>`;
      if (c === "Año" && String(v) === "2025") return `<td>2025 *</td>`;
      return `<td>${v ?? ""}</td>`;
    }).join("");
    return `<tr${cls}>${cells}</tr>`;
  }).join("");

  return `
    <div class="ba-stats-titulo">${titulo}</div>
    <div class="ba-table-wrap">
      <table class="ba-table">
        <thead><tr>${headers}</tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
    </div>`;
}

function renderGrafico(totales) {
  const rows = totales.filter(r => String(r["Año"]) !== "TOTAL" && String(r["Año"]) !== "Sin año");
  if (rows.length === 0) return;
  const ctx = document.getElementById("ba-chart");
  if (!ctx) return;
  if (_chartInstance) { _chartInstance.destroy(); _chartInstance = null; }

  _chartInstance = new Chart(ctx.getContext("2d"), {
    type: "bar",
    data: {
      labels: rows.map(r => String(r["Año"]) === "2025" ? "2025 *" : r["Año"]),
      datasets: [
        { label: "Nº Proyectos", data: rows.map(r => r["Proyectos"] || 0), backgroundColor: "#4472C4" },
        { label: "IP Hombre",    data: rows.map(r => r["Hombres"]   || 0), backgroundColor: "#ED7D31" },
        { label: "IP Mujer",     data: rows.map(r => r["Mujeres"]   || 0), backgroundColor: "#70AD47" },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: "bottom", labels: { font: { size: 10 } } },
      },
      scales: {
        y: { beginAtZero: true, ticks: { font: { size: 10 } } },
        x: { ticks: { font: { size: 10 } } },
      },
    },
  });
}

function renderDesglose(data) {
  if (!data.terminos_proyectos || data.terminos_proyectos.length === 0) return "";

  const anos = data.anos.filter(a => a !== "TOTAL");

  return `
    <h3>Nº de Proyectos por término y año</h3>
    <div class="ba-table-wrap">${renderTablaTerminos(data.terminos_proyectos, anos, false)}</div>
    <p class="ba-table-nota">* Un mismo proyecto puede aparecer en varios términos. &nbsp;|&nbsp; * 2025: Convocatorias pendientes de resolver.</p>

    <h3>Presupuesto Concedido (M€) por término y año</h3>
    <div class="ba-table-wrap">${renderTablaTerminos(data.terminos_ayuda, anos, true)}</div>
    <p class="ba-table-nota">* El presupuesto se contabiliza en cada término que contiene el proyecto. &nbsp;|&nbsp; * 2025: Convocatorias pendientes de resolver.</p>
  `;
}

function renderTablaTerminos(filas, anos, esEuros) {
  const fmtVal = v => esEuros ? formatMillonesNum(v) : formatInt(v || 0);

  const cols = ["Término", ...anos, "TOTAL"];

  const headers = cols.map((h, i) => {
    const label = String(h) === "2025" ? "2025 *" : h;
    return `<th${i === cols.length - 1 ? ' class="col-total"' : ""}>${label}</th>`;
  }).join("");

  const rows = filas.map(fila => {
    const cells = cols.map((col, ci) => {
      const val = fila[col];
      if (ci === 0) return `<td>${val}</td>`;
      const cls = ci === cols.length - 1 ? ' class="col-total"' : "";
      return `<td${cls}>${fmtVal(val)}</td>`;
    }).join("");
    return `<tr>${cells}</tr>`;
  }).join("");

  return `<table class="ba-table">
    <thead><tr>${headers}</tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

// ── Helpers de UI ─────────────────────────────────────────────────────────────

function mostrarProgreso(msg) {
  document.getElementById("ba-progress-msg").textContent = msg;
  document.getElementById("ba-progress").hidden = false;
}
function ocultarProgreso() {
  document.getElementById("ba-progress").hidden = true;
}
function mostrarError(msg) {
  const el = document.getElementById("ba-error");
  el.textContent = "⚠ " + msg;
  el.hidden = false;
}
function ocultarError() {
  document.getElementById("ba-error").hidden = true;
}
function ocultarResultado() {
  document.getElementById("ba-result").hidden = true;
}
function mostrarVacio() {
  document.getElementById("ba-empty").hidden = false;
}
function ocultarVacio() {
  document.getElementById("ba-empty").hidden = true;
}

// ── Inicialización ────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  // Estado inicial correcto
  document.getElementById("ba-progress").hidden = true;
  document.getElementById("ba-result").hidden   = true;
  document.getElementById("ba-error").hidden    = true;
  document.getElementById("ba-empty").hidden    = false;

  // Enter en los textarea dispara la búsqueda (Shift+Enter = nueva línea)
  ["or-terms", "and-terms"].forEach(id => {
    document.getElementById(id).addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        buscar();
      }
    });
  });

  log("Buscador listo.");
});
