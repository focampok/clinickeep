"""Pruebas de las rutas de lectura (publicas) y del dashboard."""

from conftest import AUTORIZADO


def test_latest_vacio(cliente):
    datos = cliente.get("/api/latest").json()
    assert datos == {"event": None, "count": 0}


def test_latest_con_datos(cliente, estado):
    cliente.post("/ingest", json=estado, headers=AUTORIZADO)
    datos = cliente.get("/api/latest").json()
    assert datos["count"] == 1
    assert datos["event"]["mode"] == "NORMAL"
    assert datos["event"]["relay_a"] is True      # A nunca se corta


def test_events_vacio_y_limite(cliente, estado):
    assert cliente.get("/api/events").json() == {"events": [], "count": 0}

    for i in range(5):
        cliente.post("/ingest", json=dict(estado, t_ms=i), headers=AUTORIZADO)

    datos = cliente.get("/api/events?limit=3").json()
    assert datos["count"] == 5                    # el total no depende del limite
    assert len(datos["events"]) == 3
    assert [e["t_ms"] for e in datos["events"]] == [2, 3, 4]   # los 3 ultimos, en orden

    # Un limite absurdo no rompe nada (se acota).
    assert cliente.get("/api/events?limit=99999").status_code == 200
    assert cliente.get("/api/events?limit=0").status_code == 200


def test_lectura_publica_sin_token(cliente):
    """Las rutas de lectura no piden token."""
    assert cliente.get("/api/latest").status_code == 200
    assert cliente.get("/api/events").status_code == 200
    assert cliente.get("/healthz").status_code == 200


def test_healthz(cliente, estado):
    datos = cliente.get("/healthz").json()
    assert datos["status"] == "ok"
    assert datos["events"] == 0
    assert datos["simulado"] is True

    cliente.post("/ingest", json=estado, headers=AUTORIZADO)
    assert cliente.get("/healthz").json()["events"] == 1


def test_dashboard_se_sirve(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "DATOS SIMULADOS" in r.text          # el banner permanente
    assert "sin relé: nunca se corta" in r.text # A explicita
    assert "prefers-color-scheme" in r.text     # tema claro/oscuro


def test_estaticos_publicados(cliente):
    """Los mapas y CSV que publica tools/publish_scenarios.py se sirven."""
    assert cliente.get("/static/scenarios.json").status_code == 200
    assert cliente.get("/static/img/s2a_mejora.png").status_code == 200
    r = cliente.get("/static/csv/s2a_mejora.csv")
    assert r.status_code == 200
    assert "mejora_pct" in r.text               # cabecera del CSV


def test_calculadora_publicada(cliente):
    """La calculadora que publica tools/publish_calc.py se sirve en /calc.

    La copia vive DENTRO de server/ (server/static/calc/), asi que esta prueba
    no necesita que calc/ este al lado.
    """
    r = cliente.get("/calc")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "SIMULACIÓN" in r.text                    # el banner
    assert "prefers-color-scheme" in r.text          # claro/oscuro

    # El modulo viaja con la pagina: /calc tiene que ser autocontenido.
    js = cliente.get("/calc/calc.js")
    assert js.status_code == 200
    assert "export function simular" in js.text


def test_el_panel_enlaza_a_la_calculadora(cliente):
    assert 'href="/calc"' in cliente.get("/").text


def test_el_panel_avisa_del_forro_de_hielo(cliente):
    """La nota fija de alcance del holdover viaja con el panel (Fase 4b, punto 3).

    La misma frase esta en calc/index.html y en calc.js: tests/test_calc_js.py
    comprueba que las tres copias dicen lo mismo.
    """
    html = cliente.get("/").text
    assert 'role="note"' in html
    assert "sin forro de hielo (holdover corto)" in html
    assert "necesitan menos ayuda" in html


def test_cors_cerrado_por_defecto(cliente):
    """Sin ALLOWED_ORIGINS no se abre CORS, ni siquiera al propio host."""
    r = cliente.get("/api/latest", headers={"Origin": "http://ejemplo.invalido"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_cors_permite_el_origen_configurado(cliente, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://panel.example")
    r = cliente.get("/api/latest", headers={"Origin": "https://panel.example"})
    assert r.headers.get("access-control-allow-origin") == "https://panel.example"
    r = cliente.get("/api/latest", headers={"Origin": "https://otro.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_la_respuesta_no_contiene_el_token(cliente, estado):
    """Ni las respuestas ni (por construccion) los logs exponen el token."""
    from conftest import TOKEN
    r = cliente.post("/ingest", json=estado, headers=AUTORIZADO)
    assert TOKEN not in r.text
    assert TOKEN not in cliente.get("/api/latest").text
    assert TOKEN not in cliente.get("/healthz").text
