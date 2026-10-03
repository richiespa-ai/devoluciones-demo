"""Genera una base de datos de demostración con pedidos y solicitudes inventados.

Uso:  python -m app.seed
Siempre genera los mismos datos (semilla fija) para que la demo sea reproducible.
Los emails usan el dominio reservado example.com: no pertenecen a nadie.
"""
from __future__ import annotations

import random
import unicodedata
from datetime import date, datetime, timedelta

from app import catalogos as cat
from app.db import DB_PATH, connect, init_schema

NOMBRES = ["Ana", "Luis", "María", "Carlos", "Laura", "Javier", "Paula", "Daniel", "Sofía", "Hugo",
           "Irene", "Álvaro", "Nuria", "Sergio", "Claudia", "Diego", "Alba", "Marcos", "Noelia", "Rubén",
           "Lorena", "Adrián", "Cristina", "Óscar", "Beatriz", "Mario", "Silvia", "Víctor", "Raquel", "Tomás"]
APELLIDOS = ["García", "López", "Sánchez", "Pérez", "Gómez", "Fernández", "Díaz", "Moreno", "Muñoz", "Álvarez",
             "Romero", "Alonso", "Gutiérrez", "Torres", "Domínguez", "Vázquez", "Ramos", "Serrano", "Blanco", "Suárez"]

PRECIOS = {"Digital": (900, 3200), "FP": (1500, 4200), "Oposiciones": (600, 1800),
           "Salud": (700, 2400), "Idiomas": (300, 1100)}
PESO_ESCUELA = {"Digital": 30, "FP": 25, "Oposiciones": 20, "Salud": 15, "Idiomas": 10}

INICIO = date(2025, 1, 1)
N_PEDIDOS = 4000
TASA_SOLICITUD = 0.11


def _slug(txt: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return sin_tildes.lower().replace(" ", "")


def generar(hoy: date | None = None, seed: int = 42) -> None:
    hoy = hoy or date.today()
    rnd = random.Random(seed)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = connect()
    init_schema(conn)

    dias_totales = (hoy - INICIO).days
    escuelas = list(PESO_ESCUELA)
    pesos = list(PESO_ESCUELA.values())
    pedidos, solicitudes = [], []
    usados: set[str] = set()

    for i in range(N_PEDIDOS):
        np_ = 100001 + i
        nombre, apellido = rnd.choice(NOMBRES), rnd.choice(APELLIDOS)
        email = f"{_slug(nombre)}.{_slug(apellido)}@example.com"
        n = 2
        while email in usados and rnd.random() < 0.85:   # algún alumno repite compra
            email = f"{_slug(nombre)}.{_slug(apellido)}{n}@example.com"
            n += 1
        usados.add(email)
        escuela = rnd.choices(escuelas, pesos)[0]
        lo, hi = PRECIOS[escuela]
        fecha = INICIO + timedelta(days=rnd.randint(0, dias_totales))
        metodo = rnd.choices(cat.METODOS_PAGO, [50, 15, 15, 20])[0]
        pedidos.append((
            np_, email, f"{nombre} {apellido}", fecha.isoformat(), escuela,
            rnd.choice(cat.ESCUELAS[escuela]), round(rnd.uniform(lo, hi) / 10) * 10,
            metodo, rnd.choice([3, 6, 12]) if metodo == "Financiación" else 1,
            rnd.choice(cat.COMERCIALES),
        ))

        if rnd.random() > TASA_SOLICITUD:
            continue
        f_sol = fecha + timedelta(days=min(int(rnd.expovariate(1 / 18)) + 1, 120))
        if f_sol > hoy:
            continue
        antiguedad = (hoy - f_sol).days
        if antiguedad < 7:
            estado = rnd.choice(["Abierta", "En gestión"])
        elif antiguedad < 20:
            estado = rnd.choices(cat.ESTADOS, [10, 30, 60])[0]
        else:
            estado = "Cerrada"
        accion, devuelto, f_reemb = "", 0.0, None
        importe = pedidos[-1][6]
        if estado == "Cerrada":
            accion = rnd.choices(cat.ACCIONES, [38, 17, 30, 15])[0]
            if accion in cat.ACCIONES_CON_DEVOLUCION:
                devuelto = importe if accion == "Devolución total" else round(importe * rnd.uniform(0.2, 0.7), 2)
                f_reemb = min(f_sol + timedelta(days=rnd.randint(2, 15)), hoy).isoformat()
        ultima = f_reemb or (f_sol + timedelta(days=rnd.randint(0, 5))).isoformat()
        solicitudes.append((
            np_, f_sol.isoformat(), rnd.choice(cat.ORIGENES), rnd.choice(cat.MOTIVOS), "",
            estado, accion, rnd.choice(cat.AGENTES), devuelto, f_reemb, "",
            min(ultima, hoy.isoformat()),
        ))

    conn.executemany("INSERT INTO pedidos VALUES (?,?,?,?,?,?,?,?,?,?)", pedidos)
    conn.executemany(
        """INSERT INTO solicitudes (np, fecha_solicitud, origen, motivo, detalle, estado, accion, agente,
                                    importe_devuelto, fecha_reembolso, comentario, actualizado)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        solicitudes,
    )
    conn.commit()
    conn.close()
    print(f"{datetime.now():%H:%M:%S}  {len(pedidos)} pedidos y {len(solicitudes)} solicitudes en {DB_PATH}")


if __name__ == "__main__":
    generar()
