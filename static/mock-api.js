"use strict";
// Versión sin servidor (GitHub Pages): imita la API de app/main.py en el navegador.
// Los datos vienen de demo-data.js y los cambios se guardan solo en este navegador (localStorage).
// Las reglas de negocio son las mismas que las de la API en Python.

(() => {
  const D = window.DEMO_DATA;
  const KEY = "devoluciones-demo:v1";
  const ESTADOS = D.catalogos.estados;
  const DEVOLUCION = ["Devolución total", "Devolución parcial"];
  const hoy = () => new Date().toISOString().slice(0, 10);

  const pedidos = new Map(D.pedidos.map((p) => [p.np, p]));
  let solicitudes = D.solicitudes;
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || "null");
    if (saved && saved.base === D.generado) solicitudes = saved.solicitudes;
  } catch { /* sin localStorage: se trabaja en memoria */ }

  const guardar = () => {
    try { localStorage.setItem(KEY, JSON.stringify({ base: D.generado, solicitudes })); } catch { /* nada */ }
  };

  class ApiError extends Error {}
  const fail = (msg) => { throw new ApiError(msg); };

  const diasEntre = (a, b) => Math.round((Date.parse(a) - Date.parse(b)) / 86400000);
  const conPedido = (s) => {
    const p = pedidos.get(s.np);
    return { ...s, email: p.email, alumno: p.alumno, fecha_compra: p.fecha_compra, escuela: p.escuela,
      programa: p.programa, importe: p.importe, metodo_pago: p.metodo_pago, comercial: p.comercial,
      dias_desde_compra: diasEntre(s.fecha_solicitud, p.fecha_compra) };
  };
  const porId = (id) => solicitudes.find((s) => s.id === id) || fail(`No existe la solicitud ${id}`);
  const ordenar = (a, b) => (b.fecha_solicitud.localeCompare(a.fecha_solicitud) || b.id - a.id);

  function listar(q) {
    const y = q.get("year");
    const texto = (q.get("q") || "").trim().toLowerCase();
    return solicitudes.map(conPedido).filter((s) =>
      s.fecha_solicitud.startsWith(y)
      && (!q.get("escuela") || s.escuela === q.get("escuela"))
      && (!q.get("estado") || s.estado === q.get("estado"))
      && (!texto || s.email.includes(texto) || s.alumno.toLowerCase().includes(texto) || String(s.np).includes(texto)),
    ).sort(ordenar);
  }

  function crear(body) {
    const np = Number(body.np);
    if (!pedidos.has(np)) fail(`No existe el pedido ${np}`);
    for (const [campo, lista] of [["origen", D.catalogos.origenes], ["motivo", D.catalogos.motivos], ["agente", D.catalogos.agentes]]) {
      if (!lista.includes(body[campo])) fail(`Valor no válido en ${campo}`);
    }
    const abierta = solicitudes.find((s) => s.np === np && s.estado !== "Cerrada");
    if (abierta) fail(`El pedido ya tiene una solicitud abierta (nº ${abierta.id})`);
    const s = {
      id: Math.max(0, ...solicitudes.map((x) => x.id)) + 1, np, fecha_solicitud: hoy(),
      origen: body.origen, motivo: body.motivo, detalle: String(body.detalle || "").slice(0, 500).trim(),
      estado: "Abierta", accion: "", agente: body.agente, importe_devuelto: 0, fecha_reembolso: null,
      comentario: String(body.comentario || "").slice(0, 500).trim(), actualizado: hoy(),
    };
    solicitudes.push(s);
    guardar();
    return conPedido(s);
  }

  function cambiar(id, body) {
    const actual = porId(id);
    const importe = pedidos.get(actual.np).importe;
    const n = { ...actual, ...body };
    if (!ESTADOS.includes(n.estado)) fail("Estado no válido");
    if (n.estado === "Cerrada" && !n.accion) fail("Para cerrar la solicitud indica el resultado (acción)");
    if (n.estado !== "Cerrada") n.accion = "";
    if (n.accion === "Devolución total") n.importe_devuelto = importe;
    else if (n.accion === "Devolución parcial") {
      if (!(n.importe_devuelto > 0 && n.importe_devuelto < importe)) {
        fail(`La devolución parcial debe estar entre 0 y ${importe.toFixed(2)} €`);
      }
    } else n.importe_devuelto = 0;
    n.fecha_reembolso = DEVOLUCION.includes(n.accion) ? (actual.fecha_reembolso || hoy()) : null;
    n.importe_devuelto = Math.round(Number(n.importe_devuelto) * 100) / 100;
    n.comentario = String(n.comentario || "").slice(0, 500).trim();
    n.actualizado = hoy();
    solicitudes[solicitudes.indexOf(actual)] = n;
    guardar();
    return conPedido(n);
  }

  function reporting(year) {
    const y = String(year);
    const campos = ["pedidos", "ventas", "solicitudes", "abiertas", "devueltas", "retenidas", "bajas_sin_devolucion", "importe_devuelto"];
    const vacio = () => Object.fromEntries(campos.map((c) => [c, 0]));
    const escuelas = D.catalogos.escuelas;
    const mensual = Object.fromEntries(escuelas.map((es) => [es, Object.fromEntries([...Array(12)].map((_, i) => [i + 1, vacio()]))]));
    const mes = (iso) => Number(iso.slice(5, 7));

    for (const p of D.pedidos) {
      if (!p.fecha_compra.startsWith(y)) continue;
      const c = mensual[p.escuela][mes(p.fecha_compra)];
      c.pedidos += 1;
      c.ventas += p.importe;
    }
    const motivos = {};
    for (const s of solicitudes) {
      const es = pedidos.get(s.np).escuela;
      if (s.fecha_solicitud.startsWith(y)) {
        const c = mensual[es][mes(s.fecha_solicitud)];
        c.solicitudes += 1;
        if (s.estado !== "Cerrada") c.abiertas += 1;
        if (DEVOLUCION.includes(s.accion)) c.devueltas += 1;
        if (s.accion === "Retenido") c.retenidas += 1;
        if (s.accion === "Baja sin devolución") c.bajas_sin_devolucion += 1;
        motivos[s.motivo] = (motivos[s.motivo] || 0) + 1;
      }
      if (s.fecha_reembolso && s.fecha_reembolso.startsWith(y)) {
        mensual[es][mes(s.fecha_reembolso)].importe_devuelto += s.importe_devuelto;
      }
    }

    const round = (v, d) => Math.round(v * 10 ** d) / 10 ** d;
    const ratios = (t) => {
      const cerradas = t.devueltas + t.retenidas + t.bajas_sin_devolucion;
      return {
        pct_importe_devuelto: t.ventas ? round(100 * t.importe_devuelto / t.ventas, 2) : 0,
        pct_solicitudes: t.pedidos ? round(100 * t.solicitudes / t.pedidos, 2) : 0,
        pct_retencion: cerradas ? round(100 * t.retenidas / cerradas, 1) : 0,
      };
    };
    const totales = vacio();
    const por_escuela = {};
    for (const es of escuelas) {
      const acum = vacio();
      for (const c of Object.values(mensual[es])) for (const k of campos) acum[k] += c[k];
      for (const k of campos) totales[k] += acum[k];
      por_escuela[es] = { ...acum, ...ratios(acum) };
    }
    return {
      year, escuelas, mensual, por_escuela,
      totales: { ...totales, ...ratios(totales) },
      por_motivo: Object.entries(motivos).map(([motivo, n]) => ({ motivo, n })).sort((a, b) => b.n - a.n),
    };
  }

  window.mockApi = async (path, opts = {}) => {
    const url = new URL(path, location.origin);
    const p = url.pathname;
    const q = url.searchParams;
    const method = (opts.method || "GET").toUpperCase();
    const body = opts.body ? JSON.parse(opts.body) : {};
    let m;
    if (p === "/api/years") return [...new Set(D.pedidos.map((x) => Number(x.fecha_compra.slice(0, 4))))].sort((a, b) => b - a);
    if (p === "/api/catalogos") return D.catalogos;
    if ((m = p.match(/^\/api\/pedidos\/(\d+)$/))) return pedidos.get(Number(m[1])) || fail(`No existe el pedido ${m[1]}`);
    if (p === "/api/pedidos") {
      const email = (q.get("email") || "").trim().toLowerCase();
      const r = D.pedidos.filter((x) => x.email === email).sort((a, b) => b.fecha_compra.localeCompare(a.fecha_compra)).slice(0, 20);
      return r.length ? r : fail("No hay pedidos con ese email");
    }
    if (p === "/api/solicitudes" && method === "GET") return listar(q);
    if (p === "/api/solicitudes" && method === "POST") return crear(body);
    if ((m = p.match(/^\/api\/solicitudes\/(\d+)$/)) && method === "PATCH") return cambiar(Number(m[1]), body);
    if (p === "/api/reporting") return reporting(Number(q.get("year")));
    return fail("Ruta no encontrada");
  };

  // Aviso y botón para volver a los datos iniciales
  const banner = document.querySelector(".banner");
  if (banner) {
    banner.textContent = "Demo con datos inventados. Los cambios que hagas se guardan solo en tu navegador. ";
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "link";
    reset.textContent = "Restablecer datos";
    reset.addEventListener("click", () => {
      try { localStorage.removeItem(KEY); } catch { /* nada */ }
      location.reload();
    });
    banner.append(reset);
  }
})();
