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

function formatInt(n) {
  return new Intl.NumberFormat("es-ES").format(Math.round(n));
}

// ── Acciones principales ─────────────────────────────────────────────────────

async function buscar() {
  const keywords = parsearTerminos(document.getElementById("or-terms").value);
  const andTerms = parsearTerminos(document.getElementById("and-terms").value);

  if (keywords.length === 0) {
    mostrarError("Introduce al menos un término de búsqueda.");
    return;
  }

  _lastRequest = { keywords, and_terms: andTerms };

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
      body: JSON.stringify({ keywords, and_terms: andTerms }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Error ${resp.status}`);
    }

    const data = await resp.json();
    log(`Encontrados: ${formatInt(data.n_proyectos)} proyectos`);
    log(`Ayuda total: ${formatEuros(data.ayuda_total)}`);
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
    log(`ERROR al generar ${tipoLabel}: ${e.message}`);
    mostrarError(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = textoOriginal;
  }
}

function limpiar() {
  document.getElementById("or-terms").value  = "";
  document.getElementById("and-terms").value = "";
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
    `${formatInt(data.n_proyectos)} proyectos &nbsp;·&nbsp; Ayuda total: ${formatEuros(data.ayuda_total)}`;

  document.getElementById("ba-desglose").innerHTML = renderDesglose(data);
  document.getElementById("ba-result").hidden = false;
}

function renderDesglose(data) {
  if (!data.terminos_proyectos || data.terminos_proyectos.length === 0) return "";

  const anos = data.anos.filter(a => a !== "TOTAL");

  return `
    <h3>Nº de Proyectos por término y año</h3>
    <div class="ba-table-wrap">${renderTablaTerminos(data.terminos_proyectos, anos, false)}</div>
    <p class="ba-table-nota">* Un mismo proyecto puede aparecer en varios términos.</p>

    <h3>Presupuesto Concedido (€) por término y año</h3>
    <div class="ba-table-wrap">${renderTablaTerminos(data.terminos_ayuda, anos, true)}</div>
    <p class="ba-table-nota">* El presupuesto se contabiliza en cada término que contiene el proyecto.</p>
  `;
}

function renderTablaTerminos(filas, anos, esEuros) {
  const fmtVal = v => esEuros
    ? new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 }).format(v || 0) + " €"
    : formatInt(v || 0);

  const cols = ["Término", ...anos, "TOTAL"];

  const headers = cols.map((h, i) =>
    `<th${i === cols.length - 1 ? ' class="col-total"' : ""}>${h}</th>`
  ).join("");

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
