"use strict";

// ────────────────────────────────────────────────────────────
// Utilidades
// ────────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const eur = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const eur2 = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
const num = new Intl.NumberFormat("es-ES");
const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

const fecha = (iso) => (iso ? iso.split("-").reverse().join("/") : "");
const pct = (v) => `${num.format(v)} %`;

async function api(path, opts = {}) {
  // En GitHub Pages no hay servidor: mock-api.js responde con los mismos datos y reglas.
  if (window.mockApi) return window.mockApi(path, opts);
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    let msg = body.detail;
    if (Array.isArray(msg)) msg = msg.map((d) => d.msg).join(". ");
    throw new Error(msg || `Error ${res.status}`);
  }
  return body;
}

/** Crea un elemento con texto seguro (nunca innerHTML con datos). */
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children) node.append(c instanceof Node ? c : document.createTextNode(c ?? ""));
  return node;
}

function fillSelect(select, values, placeholder) {
  select.replaceChildren();
  if (placeholder !== undefined) select.append(el("option", { value: "" }, placeholder));
  for (const v of values) select.append(el("option", { value: v }, v));
}

function debounce(fn, ms = 300) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function toast(text) {
  const t = $("#toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 2800);
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// ────────────────────────────────────────────────────────────
// Estado
// ────────────────────────────────────────────────────────────
const state = { year: null, cat: null, charts: {}, view: "resumen" };

// ────────────────────────────────────────────────────────────
// Pestañas
// ────────────────────────────────────────────────────────────
function setView(view) {
  state.view = view;
  document.querySelectorAll(".tabs button").forEach((b) =>
    b.setAttribute("aria-selected", String(b.dataset.view === view)));
  document.querySelectorAll(".view").forEach((s) => (s.hidden = s.id !== `view-${view}`));
  history.replaceState(null, "", `#${view}`);
  refresh();
}

function refresh() {
  if (state.view === "resumen" || state.view === "reporting") loadReporting();
  if (state.view === "solicitudes") loadSolicitudes();
}

// ────────────────────────────────────────────────────────────
// Resumen y reporting
// ────────────────────────────────────────────────────────────
async function loadReporting() {
  try {
    const rep = await api(`/api/reporting?year=${state.year}`);
    if (state.view === "resumen") renderResumen(rep);
    else renderReporting(rep);
  } catch (e) {
    toast(`No se pudo cargar el reporting: ${e.message}`);
  }
}

function renderResumen(rep) {
  const t = rep.totales;
  const kpis = [
    ["Ventas", eur.format(t.ventas), `${num.format(t.pedidos)} pedidos`],
    ["Solicitudes", num.format(t.solicitudes), `${pct(t.pct_solicitudes)} de los pedidos`],
    ["Importe devuelto", eur.format(t.importe_devuelto), `${pct(t.pct_importe_devuelto)} de las ventas`],
    ["Retención", pct(t.pct_retencion), `${num.format(t.retenidas)} alumnos retenidos`],
    ["Abiertas", num.format(t.abiertas), "pendientes de cerrar"],
  ];
  $("#kpis").replaceChildren(...kpis.map(([label, value, hint]) =>
    el("div", { class: "kpi" }, el("div", { class: "label" }, label),
      el("div", { class: "value" }, value), el("div", { class: "hint" }, hint))));

  if (!window.Chart) return; // si el CDN no carga, al menos se ven los KPIs
  const palette = ["#2f6fde", "#1f8a5b", "#b7791f", "#9b51e0", "#c2413b"];
  const text = cssVar("--muted");
  const grid = cssVar("--border");
  Chart.defaults.color = text;
  Chart.defaults.borderColor = grid;
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

  const draw = (id, config) => {
    state.charts[id]?.destroy();
    state.charts[id] = new Chart(document.getElementById(id), {
      ...config,
      options: { responsive: true, maintainAspectRatio: false, ...config.options },
    });
  };

  draw("ch-mes", {
    type: "bar",
    data: {
      labels: MESES,
      datasets: rep.escuelas.map((es, i) => ({
        label: es,
        data: MESES.map((_, m) => rep.mensual[es][m + 1].importe_devuelto),
        backgroundColor: palette[i % palette.length],
      })),
    },
    options: {
      scales: { x: { stacked: true }, y: { stacked: true, ticks: { callback: (v) => eur.format(v) } } },
      plugins: { tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${eur.format(c.raw)}` } } },
    },
  });

  draw("ch-resultado", {
    type: "doughnut",
    data: {
      labels: ["Devueltas", "Retenidas", "Baja sin devolución"],
      datasets: [{
        data: [t.devueltas, t.retenidas, t.bajas_sin_devolucion],
        backgroundColor: [palette[4], palette[1], palette[2]],
        borderWidth: 0,
      }],
    },
    options: { plugins: { legend: { position: "right" } } },
  });

  draw("ch-escuela", {
    type: "bar",
    data: {
      labels: rep.escuelas,
      datasets: [{
        label: "% devuelto sobre ventas",
        data: rep.escuelas.map((es) => rep.por_escuela[es].pct_importe_devuelto),
        backgroundColor: palette[0],
      }],
    },
    options: {
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => pct(c.raw) } } },
      scales: { y: { ticks: { callback: (v) => `${v} %` } } },
    },
  });

  draw("ch-motivo", {
    type: "bar",
    data: {
      labels: rep.por_motivo.map((m) => m.motivo),
      datasets: [{ label: "Solicitudes", data: rep.por_motivo.map((m) => m.n), backgroundColor: palette[3] }],
    },
    options: { indexAxis: "y", plugins: { legend: { display: false } } },
  });
}

function renderReporting(rep) {
  const cols = [
    ["Escuela", (r) => r.es],
    ["Pedidos", (r) => num.format(r.pedidos), true],
    ["Ventas", (r) => eur.format(r.ventas), true],
    ["Solicitudes", (r) => num.format(r.solicitudes), true],
    ["% solic.", (r) => pct(r.pct_solicitudes), true],
    ["Devueltas", (r) => num.format(r.devueltas), true],
    ["Retenidas", (r) => num.format(r.retenidas), true],
    ["% retención", (r) => pct(r.pct_retencion), true],
    ["Importe devuelto", (r) => eur.format(r.importe_devuelto), true],
    ["% s/ ventas", (r) => pct(r.pct_importe_devuelto), true],
  ];
  const cell = (tag, txt, isNum) => el(tag, isNum ? { class: "num" } : {}, txt);
  const t1 = $("#tbl-rep-escuela");
  t1.replaceChildren(
    el("thead", {}, el("tr", {}, ...cols.map(([h, , n]) => cell("th", h, n)))),
    el("tbody", {}, ...rep.escuelas.map((es) => {
      const r = { es, ...rep.por_escuela[es] };
      return el("tr", {}, ...cols.map(([, f, n]) => cell("td", f(r), n)));
    })),
    el("tfoot", {}, el("tr", {}, ...cols.map(([, f, n]) => cell("td", f({ es: "Total", ...rep.totales }), n)))),
  );

  const t2 = $("#tbl-rep-mes");
  const totalMes = MESES.map((_, m) => rep.escuelas.reduce((s, es) => s + rep.mensual[es][m + 1].importe_devuelto, 0));
  t2.replaceChildren(
    el("thead", {}, el("tr", {}, cell("th", "Escuela"), ...MESES.map((m) => cell("th", m, true)), cell("th", "Total", true))),
    el("tbody", {}, ...rep.escuelas.map((es) => el("tr", {},
      cell("td", es),
      ...MESES.map((_, m) => cell("td", eur.format(rep.mensual[es][m + 1].importe_devuelto), true)),
      cell("td", eur.format(rep.por_escuela[es].importe_devuelto), true)))),
    el("tfoot", {}, el("tr", {}, cell("td", "Total"),
      ...totalMes.map((v) => cell("td", eur.format(v), true)),
      cell("td", eur.format(rep.totales.importe_devuelto), true))),
  );
}

// ────────────────────────────────────────────────────────────
// Solicitudes
// ────────────────────────────────────────────────────────────
const BADGE = { "Abierta": "b-abierta", "En gestión": "b-gestion", "Cerrada": "b-cerrada" };

async function loadSolicitudes() {
  const params = new URLSearchParams({ year: state.year });
  const q = $("#f-q").value.trim();
  if (q) params.set("q", q);
  if ($("#f-escuela").value) params.set("escuela", $("#f-escuela").value);
  if ($("#f-estado").value) params.set("estado", $("#f-estado").value);
  try {
    const rows = await api(`/api/solicitudes?${params}`);
    $("#f-count").textContent = `${num.format(rows.length)} solicitudes`;
    $("#tbl-sol").replaceChildren(...rows.map((r) => el("tr", { class: "click", tabindex: "0",
      onclick: () => openEdit(r),
      onkeydown: (e) => { if (e.key === "Enter") openEdit(r); } },
      el("td", {}, `#${r.id} · ${fecha(r.fecha_solicitud)}`),
      el("td", {}, String(r.np)),
      el("td", {}, r.alumno),
      el("td", {}, r.escuela),
      el("td", {}, r.motivo),
      el("td", {}, el("span", { class: `badge ${BADGE[r.estado] || ""}` }, r.estado)),
      el("td", {}, r.accion || "—"),
      el("td", { class: "num" }, r.importe_devuelto ? eur2.format(r.importe_devuelto) : "—"),
      el("td", {}, r.agente))));
    if (!rows.length) $("#tbl-sol").append(el("tr", {}, el("td", { colspan: "9", class: "muted" }, "No hay solicitudes con esos filtros.")));
  } catch (e) {
    toast(`No se pudieron cargar las solicitudes: ${e.message}`);
  }
}

function infoList(dl, pairs) {
  dl.replaceChildren(...pairs.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)]));
}

let editing = null;

function openEdit(r) {
  editing = r;
  $("#e-title").textContent = `Solicitud #${r.id}`;
  infoList($("#e-info"), [
    ["Alumno", `${r.alumno} · ${r.email}`],
    ["Pedido", `${r.np} · ${fecha(r.fecha_compra)} · ${r.programa}`],
    ["Importe", `${eur2.format(r.importe)} · ${r.metodo_pago}`],
    ["Solicitud", `${fecha(r.fecha_solicitud)} · ${r.dias_desde_compra} días tras la compra · ${r.origen}`],
    ["Comercial", r.comercial],
  ]);
  $("#e-estado").value = r.estado;
  $("#e-accion").value = r.accion;
  $("#e-importe").value = r.importe_devuelto || "";
  $("#e-agente").value = r.agente;
  $("#e-motivo").value = r.motivo;
  $("#e-comentario").value = r.comentario;
  $("#e-msg").textContent = "";
  syncEditFields();
  $("#dlg").showModal();
}

function syncEditFields() {
  const cerrada = $("#e-estado").value === "Cerrada";
  $("#e-accion").disabled = !cerrada;
  if (!cerrada) $("#e-accion").value = "";
  const accion = $("#e-accion").value;
  $("#e-importe").disabled = accion !== "Devolución parcial";
  if (accion === "Devolución total") $("#e-importe").value = editing.importe;
  else if (accion !== "Devolución parcial") $("#e-importe").value = "";
}

async function saveEdit(ev) {
  ev.preventDefault();
  const msg = $("#e-msg");
  const body = {
    estado: $("#e-estado").value,
    accion: $("#e-accion").value,
    agente: $("#e-agente").value,
    motivo: $("#e-motivo").value,
    comentario: $("#e-comentario").value,
  };
  if (body.accion === "Devolución parcial") body.importe_devuelto = Number($("#e-importe").value);
  $("#e-save").disabled = true;
  try {
    await api(`/api/solicitudes/${editing.id}`, { method: "PATCH", body: JSON.stringify(body) });
    $("#dlg").close();
    toast("Solicitud guardada");
    loadSolicitudes();
  } catch (e) {
    msg.className = "msg err";
    msg.textContent = e.message;
  } finally {
    $("#e-save").disabled = false;
  }
}

// ────────────────────────────────────────────────────────────
// Nueva solicitud (autorrelleno)
// ────────────────────────────────────────────────────────────
function showPedido(p) {
  const info = $("#n-info");
  if (!p) { info.hidden = true; return; }
  $("#n-np").value = p.np;
  $("#n-email").value = p.email;
  infoList(info, [
    ["Alumno", p.alumno],
    ["Compra", `${fecha(p.fecha_compra)} · ${p.programa}`],
    ["Escuela", p.escuela],
    ["Importe", `${eur2.format(p.importe)} · ${p.metodo_pago}${p.plazos > 1 ? ` en ${p.plazos} plazos` : ""}`],
    ["Comercial", p.comercial],
  ]);
  info.hidden = false;
}

function nuevaMsg(text, kind = "") {
  const m = $("#n-msg");
  m.className = `msg ${kind}`;
  m.textContent = text;
}

const buscarPorNp = debounce(async () => {
  const np = $("#n-np").value.trim();
  $("#n-pedidos").hidden = true;
  if (!/^\d{4,}$/.test(np)) { showPedido(null); return; }
  try {
    showPedido(await api(`/api/pedidos/${np}`));
    nuevaMsg("");
  } catch (e) {
    showPedido(null);
    nuevaMsg(e.message, "err");
  }
});

const buscarPorEmail = debounce(async () => {
  const email = $("#n-email").value.trim();
  const box = $("#n-pedidos");
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { box.hidden = true; return; }
  try {
    const pedidos = await api(`/api/pedidos?email=${encodeURIComponent(email)}`);
    nuevaMsg("");
    if (pedidos.length === 1) { box.hidden = true; showPedido(pedidos[0]); return; }
    box.replaceChildren(el("span", { class: "muted" }, "Este alumno tiene varios pedidos. Elige uno:"),
      ...pedidos.map((p) => el("button", { type: "button", "aria-pressed": "false",
        onclick: (e) => {
          box.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", "false"));
          e.currentTarget.setAttribute("aria-pressed", "true");
          showPedido(p);
        } }, `${p.np} · ${fecha(p.fecha_compra)} · ${p.programa} · ${eur.format(p.importe)}`)));
    box.hidden = false;
    showPedido(null);
  } catch (e) {
    box.hidden = true;
    showPedido(null);
    nuevaMsg(e.message, "err");
  }
});

async function crearSolicitud(ev) {
  ev.preventDefault();
  const form = ev.currentTarget;
  if ($("#n-info").hidden) { nuevaMsg("Primero elige un pedido válido.", "err"); return; }
  const data = Object.fromEntries(new FormData(form));
  data.np = Number(data.np);
  const btn = form.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    const s = await api("/api/solicitudes", { method: "POST", body: JSON.stringify(data) });
    form.reset();
    showPedido(null);
    $("#n-pedidos").hidden = true;
    nuevaMsg(`Solicitud #${s.id} creada para el pedido ${s.np}.`, "ok");
  } catch (e) {
    nuevaMsg(e.message, "err");
  } finally {
    btn.disabled = false;
  }
}

// ────────────────────────────────────────────────────────────
// Arranque
// ────────────────────────────────────────────────────────────
async function init() {
  const [years, cat] = await Promise.all([api("/api/years"), api("/api/catalogos")]);
  state.cat = cat;
  state.year = years[0];
  fillSelect($("#year"), years);
  fillSelect($("#f-escuela"), cat.escuelas, "Todas las escuelas");
  fillSelect($("#f-estado"), cat.estados, "Todos los estados");
  fillSelect($("#n-origen"), cat.origenes);
  fillSelect($("#n-agente"), cat.agentes);
  fillSelect($("#n-motivo"), cat.motivos);
  fillSelect($("#e-estado"), cat.estados);
  fillSelect($("#e-accion"), cat.acciones, "—");
  fillSelect($("#e-agente"), cat.agentes);
  fillSelect($("#e-motivo"), cat.motivos);

  $("#year").addEventListener("change", (e) => { state.year = Number(e.target.value); refresh(); });
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
  $("#f-q").addEventListener("input", debounce(loadSolicitudes));
  $("#f-escuela").addEventListener("change", loadSolicitudes);
  $("#f-estado").addEventListener("change", loadSolicitudes);
  $("#n-np").addEventListener("input", buscarPorNp);
  $("#n-email").addEventListener("input", buscarPorEmail);
  $("#ejemplo-np").addEventListener("click", () => { $("#n-np").value = "100120"; buscarPorNp(); });
  $("#form-nueva").addEventListener("submit", crearSolicitud);
  $("#e-estado").addEventListener("change", syncEditFields);
  $("#e-accion").addEventListener("change", syncEditFields);
  $("#form-edit").addEventListener("submit", saveEdit);
  $("#e-close").addEventListener("click", () => $("#dlg").close());
  $("#e-cancel").addEventListener("click", () => $("#dlg").close());

  const VIEWS = ["resumen", "solicitudes", "nueva", "reporting"];
  const fromHash = () => {
    const v = location.hash.slice(1);
    return VIEWS.includes(v) ? v : "resumen";
  };
  window.addEventListener("hashchange", () => { if (fromHash() !== state.view) setView(fromHash()); });
  setView(fromHash());
}

init().catch((e) => toast(`No se pudo iniciar la aplicación: ${e.message}`));
