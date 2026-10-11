"""conftest.py - utilidades de las pruebas del servicio (sin red real).

Nada de aqui toca la red: la ingesta se prueba con el cliente de FastAPI
(TestClient, todo en proceso) y el puente se prueba con --dry-run o con
urllib.request.urlopen sustituido por un doble.
"""

import json
import os
import sys
import tempfile

import pytest

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.dirname(SERVER_DIR)
for _p in (SERVER_DIR, RAIZ, os.path.join(RAIZ, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Antes de que nadie importe app.py: que la base por defecto NO caiga en el
# repo (si no, el import crearia <raiz>/data/ck.db al correr pytest).
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(prefix="ck-test-"), "ck.db"))

TOKEN = "token-de-prueba"
AUTORIZADO = {"Authorization": "Bearer " + TOKEN}

# Un estado real, copiado de evidence/wokwi_accept_serial.log (modo NORMAL).
ESTADO = {
    "t_ms": 6665,
    "k": 1,
    "mode": "NORMAL",
    "soc": 1.0,
    "relay_a": True,
    "relay_b": True,
    "relay_c": True,
    "aut_a_h": 12.007,
    "holdover_h": 0.534,
    "safe_h": 12.541,
    "events": [],
}

EVIDENCE = os.path.join(RAIZ, "evidence", "wokwi_accept_serial.log")


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    """Cliente de FastAPI con base y token propios de cada prueba."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "ck.db"))
    monkeypatch.setenv("INGEST_TOKEN", TOKEN)

    import app
    app.init_db()

    from fastapi.testclient import TestClient
    with TestClient(app.app) as c:
        yield c


@pytest.fixture
def estado():
    return json.loads(json.dumps(ESTADO))
