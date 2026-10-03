"""API de la demo de gestión de devoluciones.

Sirve los datos (pedidos, solicitudes, reporting) en /api/* y la web estática en /.
Todos los datos son inventados (ver app/seed.py).
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Path as PathParam, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, model_validator

from app import catalogos as cat
from app.db import DB_PATH, connect, init_schema

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Si no hay base de datos (primer arranque o despliegue nuevo), se genera la de demo.
    if not DB_PATH.exists():
        from app.seed import generar
        generar()
    else:
        conn = connect()
        init_schema(conn)
        conn.close()
    yield


app = FastAPI(title="Devoluciones · demo", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["X-Frame-Options"] = "DENY"
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; "
            "style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
    return resp


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


DB = Annotated[sqlite3.Connection, Depends(get_db)]


# ──────────────────────────────────────────────────────────────────────
# Modelos de entrada (validación)
# ──────────────────────────────────────────────────────────────────────
Estado = Literal["Abierta", "En gestión", "Cerrada"]
Accion = Literal["", "Devolución total", "Devolución parcial", "Retenido", "Baja sin devolución"]
Motivo = Literal[tuple(cat.MOTIVOS)]  # type: ignore[valid-type]
Origen = Literal[tuple(cat.ORIGENES)]  # type: ignore[valid-type]
Agente = Literal[tuple(cat.AGENTES)]  # type: ignore[valid-type]


class SolicitudNueva(BaseModel):
    np: int = Field(gt=0)
    origen: Origen
    motivo: Motivo
    detalle: str = Field("", max_length=500)
    agente: Agente
    comentario: str = Field("", max_length=500)


class SolicitudCambio(BaseModel):
    estado: Estado | None = None
    accion: Accion | None = None
    motivo: Motivo | None = None
    agente: Agente | None = None
    importe_devuelto: float | None = Field(None, ge=0)
    detalle: str | None = Field(None, max_length=500)
    comentario: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _algo_que_cambiar(self):
        if not self.model_fields_set:
            raise ValueError("No hay ningún campo que cambiar")
        return self


# ──────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/catalogos")
def catalogos():
    return {
        "escuelas": list(cat.ESCUELAS),
        "origenes": cat.ORIGENES,
        "motivos": cat.MOTIVOS,
        "estados": cat.ESTADOS,
        "acciones": cat.ACCIONES,
        "agentes": cat.AGENTES,
    }


@app.get("/api/pedidos/{np}")
def pedido(np: Annotated[int, PathParam(gt=0)], db: DB):
    row = db.execute("SELECT * FROM pedidos WHERE np = ?", (np,)).fetchone()
    if not row:
        raise HTTPException(404, f"No existe el pedido {np}")
    return dict(row)


@app.get("/api/pedidos")
def pedidos_por_email(email: EmailStr, db: DB):
    rows = db.execute(
        "SELECT * FROM pedidos WHERE email = ? ORDER BY fecha_compra DESC LIMIT 20",
        (email.strip().lower(),),
    ).fetchall()
    if not rows:
        raise HTTPException(404, "No hay pedidos con ese email")
    return [dict(r) for r in rows]


SELECT_SOLICITUD = """
    SELECT s.*, p.email, p.alumno, p.fecha_compra, p.escuela, p.programa, p.importe,
           p.metodo_pago, p.comercial,
           CAST(julianday(s.fecha_solicitud) - julianday(p.fecha_compra) AS INTEGER) AS dias_desde_compra
    FROM solicitudes s JOIN pedidos p ON p.np = s.np
"""


@app.get("/api/solicitudes")
def solicitudes(
    db: DB,
    year: int = Query(date.today().year, ge=2000, le=2100),
    escuela: str | None = None,
    estado: Estado | None = None,
    q: str | None = Query(None, max_length=100),
):
    sql = SELECT_SOLICITUD + " WHERE substr(s.fecha_solicitud, 1, 4) = ?"
    params: list = [str(year)]
    if escuela:
        sql += " AND p.escuela = ?"
        params.append(escuela)
    if estado:
        sql += " AND s.estado = ?"
        params.append(estado)
    if q:
        sql += " AND (p.email LIKE ? OR p.alumno LIKE ? OR CAST(s.np AS TEXT) LIKE ?)"
        like = f"%{q.strip()}%"
        params += [like, like, like]
    sql += " ORDER BY s.fecha_solicitud DESC, s.id DESC"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def _solicitud(db: sqlite3.Connection, sid: int) -> dict:
    row = db.execute(SELECT_SOLICITUD + " WHERE s.id = ?", (sid,)).fetchone()
    if not row:
        raise HTTPException(404, f"No existe la solicitud {sid}")
    return dict(row)


@app.post("/api/solicitudes", status_code=201)
def crear_solicitud(body: SolicitudNueva, db: DB):
    if not db.execute("SELECT 1 FROM pedidos WHERE np = ?", (body.np,)).fetchone():
        raise HTTPException(422, f"No existe el pedido {body.np}")
    abierta = db.execute(
        "SELECT id FROM solicitudes WHERE np = ? AND estado != 'Cerrada'", (body.np,)
    ).fetchone()
    if abierta:
        raise HTTPException(409, f"El pedido ya tiene una solicitud abierta (nº {abierta['id']})")
    hoy = date.today().isoformat()
    cur = db.execute(
        """INSERT INTO solicitudes (np, fecha_solicitud, origen, motivo, detalle, estado, agente,
                                    comentario, actualizado)
           VALUES (?, ?, ?, ?, ?, 'Abierta', ?, ?, ?)""",
        (body.np, hoy, body.origen, body.motivo, body.detalle.strip(), body.agente,
         body.comentario.strip(), hoy),
    )
    db.commit()
    return _solicitud(db, cur.lastrowid)


@app.patch("/api/solicitudes/{sid}")
def cambiar_solicitud(sid: Annotated[int, PathParam(gt=0)], body: SolicitudCambio, db: DB):
    actual = _solicitud(db, sid)
    nuevo = {**actual, **body.model_dump(exclude_unset=True)}

    # Reglas de negocio
    if nuevo["estado"] == "Cerrada" and not nuevo["accion"]:
        raise HTTPException(422, "Para cerrar la solicitud indica el resultado (acción)")
    if nuevo["estado"] != "Cerrada":
        nuevo["accion"] = ""
    if nuevo["accion"] == "Devolución total":
        nuevo["importe_devuelto"] = actual["importe"]
    elif nuevo["accion"] == "Devolución parcial":
        if not 0 < (nuevo["importe_devuelto"] or 0) < actual["importe"]:
            raise HTTPException(422, f"La devolución parcial debe estar entre 0 y {actual['importe']:.2f} €")
    else:
        nuevo["importe_devuelto"] = 0
    if nuevo["accion"] in cat.ACCIONES_CON_DEVOLUCION:
        nuevo["fecha_reembolso"] = actual["fecha_reembolso"] or date.today().isoformat()
    else:
        nuevo["fecha_reembolso"] = None

    db.execute(
        """UPDATE solicitudes SET estado=?, accion=?, motivo=?, agente=?, importe_devuelto=?,
                  fecha_reembolso=?, detalle=?, comentario=?, actualizado=?
           WHERE id = ?""",
        (nuevo["estado"], nuevo["accion"], nuevo["motivo"], nuevo["agente"],
         round(float(nuevo["importe_devuelto"]), 2), nuevo["fecha_reembolso"],
         (nuevo["detalle"] or "").strip(), (nuevo["comentario"] or "").strip(),
         date.today().isoformat(), sid),
    )
    db.commit()
    return _solicitud(db, sid)


@app.get("/api/years")
def years(db: DB):
    rows = db.execute(
        "SELECT DISTINCT CAST(substr(fecha_compra, 1, 4) AS INTEGER) AS y FROM pedidos ORDER BY y DESC"
    ).fetchall()
    return [r["y"] for r in rows]


@app.get("/api/reporting")
def reporting(db: DB, year: int = Query(date.today().year, ge=2000, le=2100)):
    """Indicadores por escuela y mes.

    - ventas / pedidos: por fecha de compra
    - solicitudes, retenidas, devueltas: por fecha de solicitud
    - importe_devuelto: por fecha de reembolso
    """
    y = str(year)
    escuelas = list(cat.ESCUELAS)
    campos = ("pedidos", "ventas", "solicitudes", "abiertas", "devueltas", "retenidas",
              "bajas_sin_devolucion", "importe_devuelto")
    datos = {es: {m: dict.fromkeys(campos, 0) for m in range(1, 13)} for es in escuelas}

    def sumar(sql: str, mapping: dict[str, str]):
        for r in db.execute(sql, (y,)).fetchall():
            if r["escuela"] in datos:
                celda = datos[r["escuela"]][r["mes"]]
                for campo, col in mapping.items():
                    celda[campo] += r[col] or 0

    sumar("""SELECT escuela, CAST(substr(fecha_compra,6,2) AS INTEGER) AS mes,
                    COUNT(*) AS n, SUM(importe) AS total
             FROM pedidos WHERE substr(fecha_compra,1,4) = ? GROUP BY 1, 2""",
          {"pedidos": "n", "ventas": "total"})
    sumar("""SELECT p.escuela, CAST(substr(s.fecha_solicitud,6,2) AS INTEGER) AS mes,
                    COUNT(*) AS n,
                    SUM(s.estado != 'Cerrada') AS abiertas,
                    SUM(s.accion IN ('Devolución total','Devolución parcial')) AS devueltas,
                    SUM(s.accion = 'Retenido') AS retenidas,
                    SUM(s.accion = 'Baja sin devolución') AS bajas
             FROM solicitudes s JOIN pedidos p ON p.np = s.np
             WHERE substr(s.fecha_solicitud,1,4) = ? GROUP BY 1, 2""",
          {"solicitudes": "n", "abiertas": "abiertas", "devueltas": "devueltas",
           "retenidas": "retenidas", "bajas_sin_devolucion": "bajas"})
    sumar("""SELECT p.escuela, CAST(substr(s.fecha_reembolso,6,2) AS INTEGER) AS mes,
                    SUM(s.importe_devuelto) AS devuelto
             FROM solicitudes s JOIN pedidos p ON p.np = s.np
             WHERE s.fecha_reembolso IS NOT NULL AND substr(s.fecha_reembolso,1,4) = ? GROUP BY 1, 2""",
          {"importe_devuelto": "devuelto"})

    totales = dict.fromkeys(campos, 0)
    por_escuela = {}
    for es in escuelas:
        acum = dict.fromkeys(campos, 0)
        for celda in datos[es].values():
            for c in campos:
                acum[c] += celda[c]
        por_escuela[es] = acum
        for c in campos:
            totales[c] += acum[c]

    def ratios(t: dict) -> dict:
        cerradas = t["devueltas"] + t["retenidas"] + t["bajas_sin_devolucion"]
        return {
            "pct_importe_devuelto": round(100 * t["importe_devuelto"] / t["ventas"], 2) if t["ventas"] else 0,
            "pct_solicitudes": round(100 * t["solicitudes"] / t["pedidos"], 2) if t["pedidos"] else 0,
            "pct_retencion": round(100 * t["retenidas"] / cerradas, 1) if cerradas else 0,
        }

    return {
        "year": year,
        "escuelas": escuelas,
        "mensual": datos,
        "por_escuela": {es: {**v, **ratios(v)} for es, v in por_escuela.items()},
        "totales": {**totales, **ratios(totales)},
        "por_motivo": [dict(r) for r in db.execute(
            """SELECT motivo, COUNT(*) AS n FROM solicitudes
               WHERE substr(fecha_solicitud,1,4) = ? GROUP BY motivo ORDER BY n DESC""", (y,)).fetchall()],
    }


# ──────────────────────────────────────────────────────────────────────
# Web estática
# ──────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
