// Cambia esta constante para mover el frontend a Drupal (o a otro dominio).
// Vacío = misma URL de origen (HF Spaces).
const API_BASE_URL = "";

// ── Estado de la última búsqueda (para los botones de descarga) ──────────────
let _lastRequest = null;

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
  return new Intl.NumberFormat("es-ES").format(n);
}

// ── Acciones principales ─────────────────────────────────────────────────────

async function buscar() {
  const keywords  = parsearTerminos(document.getElementById("or-terms").value);
  const andTerms  = parsearTerminos(document.getElementById("and-terms").value);

  if (keywords.length === 0) {
    mostrarError("Introduce al menos un término de búsqueda.");
    return;
  }

  _lastRequest = { keywords, and_terms: andTerms };

  ocultarError();
  ocultarResultado();
  mostrarProgreso("Buscando en la base de datos…");
  document.getElementById("btn-buscar").disabled = true;

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
    ocultarProgreso();
    mostrarResultado(data);

  } catch (e) {
    ocultarProgreso();
    mostrarError(e.message === "Failed to fetch"
      ? "No se pudo conectar con el servidor. ¿Está en marcha la API?"
      : e.message);
  } finally {
    document.getElementById("btn-buscar").disabled = false;
  }
}

async function descargar(tipo) {
  if (!_lastRequest) return;

  const endpoint = tipo === "xlsx" ? "/descargar-xlsx" : "/descargar-pdf";
  const btn = event.currentTarget;
  const textoOriginal = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Descargando…";

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

    // Crear enlace de descarga (abre el diálogo "Guardar como…" del SO)
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

  } catch (e) {
    mostrarError("Error al descargar: " + e.message);
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
  _lastRequest = null;
}

// ── Renderizado de resultados ────────────────────────────────────────────────

function mostrarResultado(data) {
  // Resumen
  const andLabel = data.and_terms.length
    ? `  AND: ${data.and_terms.join(" + ")}`
    : "";
  document.getElementById("ba-result-summary").innerHTML =
    `🔍 <strong>${data.keywords.join(" | ")}${andLabel}</strong><br>` +
    `${formatInt(data.n_proyectos)} proyectos encontrados`;

  // Desglose por término
  document.getElementById("ba-desglose").innerHTML =
    renderDesglose(data);

  document.getElementById("ba-result").hidden = false;
}

function renderDesglose(data) {
  if (!data.terminos_proyectos || data.terminos_proyectos.length === 0) return "";

  const anos = data.anos.filter(a => a !== "TOTAL");

  return `
    <h3>Nº de Proyectos por término y año</h3>
    ${renderTablaTerminos(data.terminos_proyectos, anos, false)}
    <p class="ba-table-nota">* Un mismo proyecto puede aparecer en varios términos si contiene más de uno.</p>

    <h3>Presupuesto Concedido (€) por término y año</h3>
    ${renderTablaTerminos(data.terminos_ayuda, anos, true)}
    <p class="ba-table-nota">* El presupuesto de cada proyecto se contabiliza en cada término que contiene.</p>
  `;
}

function renderTablaTerminos(filas, anos, esEuros) {
  const fmtVal = v => esEuros
    ? new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 }).format(v || 0) + " €"
    : formatInt(v || 0);

  const headers = ["Término", ...anos, "TOTAL"]
    .map((h, i) => `<th${i === anos.length + 1 ? ' class="col-total"' : ""}>${h}</th>`)
    .join("");

  const rows = filas.map((fila, ri) => {
    const cells = ["Término", ...anos, "TOTAL"].map((col, ci) => {
      const val = fila[col];
      const isTotal = ci === anos.length + 1;
      const cls = isTotal ? ' class="total"' : "";
      return ci === 0
        ? `<td>${val}</td>`
        : `<td${cls}>${fmtVal(val)}</td>`;
    }).join("");
    return `<tr>${cells}</tr>`;
  }).join("");

  return `
    <div class="ba-table-wrap">
      <table class="ba-table">
        <thead><tr>${headers}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
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

// ── Enviar con Enter en los textarea (Ctrl+Enter para nueva línea) ─────────
document.addEventListener("DOMContentLoaded", () => {
  ["or-terms", "and-terms"].forEach(id => {
    document.getElementById(id).addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        buscar();
      }
    });
  });
});
