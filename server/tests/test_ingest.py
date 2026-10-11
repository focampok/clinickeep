"""Pruebas de POST /ingest: auth, tamano, esquema y retencion."""

import json

import pytest

from conftest import (AUTORIZADO, CAMPOS_3B, LOG_NUEVO, LOG_VIEJO, TOKEN,
                      saltar_si_falta)


def _estados_del_log(ruta):
    """Parser minimo y local, para no depender de tools/ desde server/tests/.

    (El filtrado del puente se prueba aparte, en test_bridge.py, que si importa
    tools/serial_to_ingest.py y se salta entero cuando no esta.)
    """
    estados = []
    with open(ruta, encoding="utf-8", errors="replace") as fh:
        for linea in fh:
            i = linea.find("{")
            if i < 0:
                continue
            try:
                obj = json.loads(linea[i:])
            except ValueError:
                continue
            if isinstance(obj, dict) and "mode" in obj and "t_ms" in obj:
                estados.append(obj)
    return estados


@pytest.mark.parametrize("ruta,campos", [(LOG_VIEJO, 11), (LOG_NUEVO, 16)])
def test_los_logs_congelados_validan_el_esquema(ruta, campos):
    """Los dos formatos reales (11 y 16 campos) pasan el esquema del servidor."""
    saltar_si_falta(ruta)
    import app

    estados = _estados_del_log(ruta)
    assert len(estados) == 75
    for o in estados:
        assert len(o) == campos
        app.State(**o)                     # no debe lanzar ValidationError

    if campos == 16:
        assert all(o["temp_c"] is not None and o["temp_ok"] is not None for o in estados)
    else:
        assert all("temp_c" not in o and "grid_ok" not in o for o in estados)


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

    # Y el servidor no inventa campos: los que devuelve son los del firmware
    # (los 11 que manda este evento) mas los 5 opcionales de la Fase 3b, que
    # aqui llegan vacios.
    assert set(ev) == {"id", "ts_server", "simulado"} | set(estado) | set(CAMPOS_3B)


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


def test_evento_antiguo_de_11_campos_sigue_validando(cliente, estado):
    """El formato de la Fase 3 (sin los campos 3b) no se rompe."""
    assert len(estado) == 11
    assert cliente.post("/ingest", json=estado, headers=AUTORIZADO).status_code == 201

    ev = cliente.get("/api/latest").json()["event"]
    # Los campos nuevos existen en la respuesta, pero como None.
    for campo in CAMPOS_3B:
        assert campo in ev
        assert ev[campo] is None


def test_evento_nuevo_de_16_campos_valida_y_guarda_los_valores(cliente, estado_nuevo):
    """El formato de la Fase 3b trae los 5 campos nuevos y se guardan tal cual."""
    assert len(estado_nuevo) == 16
    r = cliente.post("/ingest", json=estado_nuevo, headers=AUTORIZADO)
    assert r.status_code == 201

    ev = cliente.get("/api/latest").json()["event"]
    assert ev["grid_ok"] is True
    assert ev["alarm"] is False
    assert ev["aut_total_h"] == pytest.approx(12.007)
    assert ev["temp_c"] == pytest.approx(25.0)
    assert ev["temp_ok"] is True

    # Devuelve los 16 del firmware, mas id/ts_server/simulado del servidor.
    assert set(ev) == {"id", "ts_server", "simulado"} | set(estado_nuevo)


def test_campos_3b_no_rompen_extra_forbid(cliente, estado_nuevo):
    """Sigue siendo estricto: un campo de mas da 422, aunque los 3b sean opcionales."""
    for inventado in ("humedad", "temp_c2", "grid", "alarms"):
        assert cliente.post("/ingest", json=dict(estado_nuevo, **{inventado: 1}),
                            headers=AUTORIZADO).status_code == 422

    # Y un tipo equivocado en un campo 3b tampoco pasa.
    assert cliente.post("/ingest", json=dict(estado_nuevo, temp_c="caliente"),
                        headers=AUTORIZADO).status_code == 422
    assert cliente.post("/ingest", json=dict(estado_nuevo, grid_ok="si"),
                        headers=AUTORIZADO).status_code == 422


def test_mezcla_de_formatos_en_la_misma_base(cliente, estado, estado_nuevo):
    """Un evento viejo y uno nuevo conviven, y cada uno trae lo suyo."""
    cliente.post("/ingest", json=estado, headers=AUTORIZADO)
    cliente.post("/ingest", json=dict(estado_nuevo, mode="CORTE", grid_ok=False),
                 headers=AUTORIZADO)

    viejos, nuevos = cliente.get("/api/events").json()["events"]
    assert viejos["temp_c"] is None and viejos["grid_ok"] is None
    assert nuevos["temp_c"] == pytest.approx(25.0) and nuevos["grid_ok"] is False

    # El dashboard tiene que servir tanto el evento viejo como el nuevo.
    html = cliente.get("/").text
    assert "grid_ok" in html and "temp_c" in html


def test_dos_ingestas_se_guardan_en_orden(cliente, estado):
    cliente.post("/ingest", json=estado, headers=AUTORIZADO)
    segundo = dict(estado, mode="CORTE", relay_c=False, t_ms=10000)
    cliente.post("/ingest", json=segundo, headers=AUTORIZADO)

    datos = cliente.get("/api/events").json()
    assert [e["mode"] for e in datos["events"]] == ["NORMAL", "CORTE"]
    assert datos["events"][1]["relay_c"] is False
