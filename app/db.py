"""Conexión y esquema de la base de datos SQLite."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).resolve().parent.parent / "data" / "demo.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS pedidos (
    np            INTEGER PRIMARY KEY,          -- nº de pedido
    email         TEXT    NOT NULL,
    alumno        TEXT    NOT NULL,
    fecha_compra  TEXT    NOT NULL,             -- ISO yyyy-mm-dd
    escuela       TEXT    NOT NULL,
    programa      TEXT    NOT NULL,
    importe       REAL    NOT NULL,             -- facturación en EUR
    metodo_pago   TEXT    NOT NULL,
    plazos        INTEGER NOT NULL DEFAULT 1,
    comercial     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pedidos_email ON pedidos(email);

CREATE TABLE IF NOT EXISTS solicitudes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    np               INTEGER NOT NULL REFERENCES pedidos(np),
    fecha_solicitud  TEXT    NOT NULL,
    origen           TEXT    NOT NULL,
    motivo           TEXT    NOT NULL,
    detalle          TEXT    NOT NULL DEFAULT '',
    estado           TEXT    NOT NULL,
    accion           TEXT    NOT NULL DEFAULT '',
    agente           TEXT    NOT NULL,
    importe_devuelto REAL    NOT NULL DEFAULT 0,
    fecha_reembolso  TEXT,
    comentario       TEXT    NOT NULL DEFAULT '',
    actualizado      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_solicitudes_np ON solicitudes(np);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
