"""Tests de la API. Usan una base de datos temporal generada con la misma semilla."""
import os
import tempfile
from datetime import date
from pathlib import Path

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed import generar  # noqa: E402


@pytest.fixture()
def client():
    generar(hoy=date(2026, 6, 30))
    with TestClient(app) as c:
        yield c


def pedido_sin_solicitud(client) -> dict:
    con_solicitud = {s["np"] for y in (2025, 2026) for s in client.get(f"/api/solicitudes?year={y}").json()}
    np_ = next(n for n in range(100001, 104001) if n not in con_solicitud)
    return client.get(f"/api/pedidos/{np_}").json()


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_pedido_existe_y_no_existe(client):
    assert client.get("/api/pedidos/100001").status_code == 200
    assert client.get("/api/pedidos/999999").status_code == 404


def test_pedidos_por_email(client):
    email = client.get("/api/pedidos/100001").json()["email"]
    r = client.get("/api/pedidos", params={"email": email.upper()})
    assert r.status_code == 200
    assert all(p["email"] == email for p in r.json())
    assert client.get("/api/pedidos", params={"email": "no-es-un-email"}).status_code == 422


def test_crear_solicitud_y_no_duplicar(client):
    p = pedido_sin_solicitud(client)
    body = {"np": p["np"], "origen": "Email", "motivo": "Otros", "agente": "Marta Ruiz"}
    r = client.post("/api/solicitudes", json=body)
    assert r.status_code == 201
    assert r.json()["estado"] == "Abierta"
    assert client.post("/api/solicitudes", json=body).status_code == 409


def test_crear_solicitud_valida_catalogos(client):
    p = pedido_sin_solicitud(client)
    r = client.post("/api/solicitudes", json={"np": p["np"], "origen": "Paloma mensajera",
                                              "motivo": "Otros", "agente": "Marta Ruiz"})
    assert r.status_code == 422


def test_cerrar_requiere_resultado_y_calcula_importe(client):
    p = pedido_sin_solicitud(client)
    sid = client.post("/api/solicitudes", json={"np": p["np"], "origen": "Chat", "motivo": "Otros",
                                                "agente": "Pablo Ortega"}).json()["id"]
    assert client.patch(f"/api/solicitudes/{sid}", json={"estado": "Cerrada"}).status_code == 422

    r = client.patch(f"/api/solicitudes/{sid}", json={"estado": "Cerrada", "accion": "Devolución total"})
    assert r.status_code == 200
    assert r.json()["importe_devuelto"] == p["importe"]
    assert r.json()["fecha_reembolso"]

    malo = client.patch(f"/api/solicitudes/{sid}", json={"accion": "Devolución parcial",
                                                         "importe_devuelto": p["importe"] + 1})
    assert malo.status_code == 422

    r = client.patch(f"/api/solicitudes/{sid}", json={"accion": "Retenido"})
    assert r.json()["importe_devuelto"] == 0
    assert r.json()["fecha_reembolso"] is None


def test_reporting_cuadra(client):
    rep = client.get("/api/reporting?year=2025").json()
    t = rep["totales"]
    assert t["ventas"] == pytest.approx(sum(v["ventas"] for v in rep["por_escuela"].values()))
    assert t["solicitudes"] == sum(m["n"] for m in rep["por_motivo"])
    assert 0 < t["pct_importe_devuelto"] < 100


def test_busqueda_no_rompe_con_caracteres_raros(client):
    r = client.get("/api/solicitudes", params={"year": 2025, "q": "'; DROP TABLE pedidos; --"})
    assert r.status_code == 200
    assert client.get("/api/pedidos/100001").status_code == 200
