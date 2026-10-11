"""Pruebas de POST /ingest: auth, tamano, esquema y retencion."""

import json

import pytest

from conftest import AUTORIZADO, TOKEN


def test_ingesta_valida(cliente, estado):
    r = cliente.post("/ingest", json=estado, headers=AUTORIZADO)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["ok"] is True
    assert cuerpo["simulado"] is True
    assert isinstance(cuerpo["id"], int)

    # Queda guardado, con la hora del servidor y la bandera de simulado.
    ev = cliente.get("/api/latest").json()["event"]
    assert ev["mode"] == "NORMAL"
    assert ev["simulado"] is True
    assert ev["ts_server"]
    assert ev["safe_h"] == pytest.approx(12.541)

    # Y el servidor no inventa campos: los que devuelve son los del firmware.
    assert set(ev) == {"id", "ts_server", "simulado"} | set(estado)


def test_sin_token(cliente, estado):
    r = cliente.post("/ingest", json=estado)
    assert r.status_code == 401
    assert cliente.get("/api/latest").json()["event"] is None


def test_token_erroneo(cliente, estado):
    r = cliente.post("/ingest", json=estado,
                     headers={"Authorization": "Bearer " + TOKEN + "x"})
    assert r.status_code == 401

    # Un esquema que no es Bearer tampoco pasa.
    r = cliente.post("/ingest", json=estado, headers={"Authorization": TOKEN})
    assert r.status_code == 401

    assert cliente.get("/api/latest").json()["event"] is None


def test_payload_grande(cliente, estado):
    # Un campo enorme (dentro del esquema) supera los 8 KB.
    gordo = dict(estado, events=["x" * 9000])
    r = cliente.post("/ingest", json=gordo, headers=AUTORIZADO)
    assert r.status_code == 413
    assert cliente.get("/api/latest").json()["event"] is None

    # El limite tambien se respeta sin cabecera Content-Length fiable.
    r = cliente.post("/ingest", content=b"x" * 9000, headers=AUTORIZADO)
    assert r.status_code == 413


def test_campo_desconocido(cliente, estado):
    # Un campo de mas se rechaza (esquema estricto: extra="forbid").
    r = cliente.post("/ingest", json=dict(estado, temperatura=5.0), headers=AUTORIZADO)
    assert r.status_code == 422
    assert cliente.get("/api/latest").json()["event"] is None

    # Un campo que falta tambien.
    sin_modo = {k: v for k, v in estado.items() if k != "mode"}
    assert cliente.post("/ingest", json=sin_modo, headers=AUTORIZADO).status_code == 422

    # Un modo que no existe, tambien.
    assert cliente.post("/ingest", json=dict(estado, mode="DORMIDO"),
                        headers=AUTORIZADO).status_code == 422

    # Y una soc fuera de rango, tambien.
    assert cliente.post("/ingest", json=dict(estado, soc=3.0),
                        headers=AUTORIZADO).status_code == 422


def test_json_invalido(cliente):
    r = cliente.post("/ingest", content=b"{no es json",
                     headers=dict(AUTORIZADO, **{"Content-Type": "application/json"}))
    assert r.status_code == 422


def test_sin_token_configurado_da_503(cliente, estado, monkeypatch):
    monkeypatch.setenv("INGEST_TOKEN", "")
    r = cliente.post("/ingest", json=estado, headers=AUTORIZADO)
    assert r.status_code == 503


def test_retencion_de_5000(cliente, estado):
    """Solo se conservan los ultimos 5000 eventos."""
    import app

    # La tabla se llena de golpe (5000 filas) para no hacer 5000 commits, y
    # despues se mete una mas por el camino normal: el que poda es store_event.
    relleno = [
        ("2026-01-01T00:00:00.000+00:00", 1, i, 1.0, "NORMAL", 1.0, 1, 1, 1,
         12.0, 0.5, 12.5, "[]", "{}")
        for i in range(app.MAX_EVENTS)
    ]
    conn = app._connect()
    try:
        conn.executemany(
            """INSERT INTO events (ts_server, simulado, t_ms, k, mode, soc,
                                   relay_a, relay_b, relay_c, aut_a_h,
                                   holdover_h, safe_h, events, raw)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", relleno)
        conn.commit()
    finally:
        conn.close()

    for i in range(5):
        app.store_event(app.State(**dict(estado, t_ms=100000 + i)))

    ultimo = cliente.get("/api/latest").json()
    assert ultimo["count"] == app.MAX_EVENTS          # no crece sin limite
    assert ultimo["event"]["t_ms"] == 100004

    # Los 5 del relleno con id mas bajo se podaron: el mas antiguo que queda
    # es el de t_ms=5 (los ids 1..5000 se llenaron con t_ms = id - 1).
    conn = app._connect()
    try:
        fila = conn.execute("SELECT COUNT(*) n, MIN(id) a, MIN(t_ms) t FROM events").fetchone()
    finally:
        conn.close()
    assert (fila["n"], fila["a"], fila["t"]) == (app.MAX_EVENTS, 6, 5)

    # La lectura publica acota el limite a 1000, asi que la pagina trae 1000.
    eventos = cliente.get("/api/events?limit=5000").json()["events"]
    assert len(eventos) == app.MAX_EVENTS_LIMIT
    assert eventos[-1]["t_ms"] == 100004


def test_dos_ingestas_se_guardan_en_orden(cliente, estado):
    cliente.post("/ingest", json=estado, headers=AUTORIZADO)
    segundo = dict(estado, mode="CORTE", relay_c=False, t_ms=10000)
    cliente.post("/ingest", json=segundo, headers=AUTORIZADO)

    datos = cliente.get("/api/events").json()
    assert [e["mode"] for e in datos["events"]] == ["NORMAL", "CORTE"]
    assert datos["events"][1]["relay_c"] is False
