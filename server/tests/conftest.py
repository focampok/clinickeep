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
# Formato ANTIGUO: 11 campos, el de la Fase 3.
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

# Formato NUEVO (Fase 3b): 16 campos. temp_c es la lectura del DS18B20, que en
# la maqueta esta a 25 C (el ambiente, no la caja).
CAMPOS_3B = ("grid_ok", "alarm", "aut_total_h", "temp_c", "temp_ok")
ESTADO_NUEVO = dict(ESTADO, grid_ok=True, alarm=False, aut_total_h=12.007,
                    temp_c=25.0, temp_ok=True)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
# Logs congelados: el viejo (11 campos) y el regenerado con el firmware nuevo.
LOG_VIEJO = os.path.join(DATA_DIR, "serial_viejo_11_campos.log")
LOG_NUEVO = os.path.join(DATA_DIR, "serial_nuevo_16_campos.log")

# Log vivo del repo (fuera de server/): si no esta, las pruebas que lo usan
# se saltan, para que server/ siga siendo autocontenido.
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


@pytest.fixture
def estado_nuevo():
    return json.loads(json.dumps(ESTADO_NUEVO))


def saltar_si_falta(path):
    """Las pruebas que dependen de archivos fuera de server/ no lo exigen."""
    if not os.path.exists(path):
        pytest.skip("falta %s (server/ es autocontenido sin el)" % path)
