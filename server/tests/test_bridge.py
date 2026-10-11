"""Pruebas del puente tools/serial_to_ingest.py.

Sin red real: o se usa --dry-run, o se sustituye urllib.request.urlopen por un
doble que cuenta llamadas y devuelve lo que haga falta.
"""

import io
import json
import urllib.error

import pytest

from conftest import EVIDENCE

import serial_to_ingest as puente


# --- Filtrado de lineas ------------------------------------------------------

def test_solo_pasa_estados():
    assert puente.is_state({"mode": "NORMAL", "t_ms": 1}) is True
    assert puente.is_state({"boot": "clinickeep", "relays": "open"}) is False
    assert puente.is_state({"boot_ready": True}) is False
    assert puente.is_state({"cmd": "GRID0"}) is False
    assert puente.is_state({"cmd": "K", "k": 600}) is False
    assert puente.is_state({"mode": "NORMAL"}) is False      # sin t_ms no es estado
    assert puente.is_state({"hola": 1}) is False


def test_extrae_json_con_prefijo():
    assert puente.extract_json('{"mode":"NORMAL","t_ms":1}') == {"mode": "NORMAL", "t_ms": 1}
    assert puente.extract_json('> prefijo {"mode":"CORTE","t_ms":2}') == {"mode": "CORTE", "t_ms": 2}
    assert puente.extract_json("ets Jul 29 2019 rst:0x1 (POWERON_RESET)") is None
    assert puente.extract_json("") is None
    assert puente.extract_json("[1, 2, 3]") is None          # JSON, pero no objeto


def test_dry_run_con_el_log_de_evidencia(capsys, tmp_path):
    """Con las lineas reales de evidence/: 75 estados y nada de boot ni cmd."""
    codigo = puente.main(["--file", EVIDENCE, "--dry-run"])
    salida = capsys.readouterr()
    assert codigo == 0

    lineas = [l for l in salida.out.splitlines() if l.strip()]
    assert len(lineas) == 75
    objetos = [json.loads(l) for l in lineas]
    assert all("mode" in o and "t_ms" in o for o in objetos)
    assert all(o.get("cmd") is None and o.get("boot") is None for o in objetos)

    # El resumen va a stderr y cuadra con el censo del log.
    assert "estados 75 | enviados 75 | fallidos 0 | lineas ignoradas 16" in salida.err
    # En dry-run no se envia nada: nada de peticiones.
    assert "no se envia nada" in salida.err


def test_dry_run_de_un_archivo_mezclado(capsys, tmp_path):
    mezcla = tmp_path / "mezcla.log"
    mezcla.write_text(
        'ets Jul 29 2019 12:21:46\n'
        '{"boot":"clinickeep","relays":"open"}\n'
        '{"boot_ready":true}\n'
        '{"cmd":"GRID0"}\n'
        '{"cmd":"K","k":600}\n'
        '{"t_ms":1,"k":1,"mode":"NORMAL","soc":1.0,"relay_a":true,"relay_b":true,'
        '"relay_c":true,"aut_a_h":12.0,"holdover_h":0.5,"safe_h":12.5,"events":[]}\n'
        'linea suelta sin json\n',
        encoding="utf-8")
    assert puente.main(["--file", str(mezcla), "--dry-run"]) == 0
    salida = capsys.readouterr()
    assert len([l for l in salida.out.splitlines() if l.strip()]) == 1
    assert "estados 1 | enviados 1 | fallidos 0 | lineas ignoradas 6" in salida.err


def test_dry_run_desde_stdin(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(
        '{"boot_ready":true}\n'
        '{"t_ms":9,"k":1,"mode":"CORTE","soc":0.5,"relay_a":true,"relay_b":true,'
        '"relay_c":false,"aut_a_h":6.0,"holdover_h":0.5,"safe_h":6.5,"events":[]}\n'))
    assert puente.main(["--dry-run"]) == 0
    salida = capsys.readouterr()
    assert '"mode": "CORTE"' in salida.out
    assert "boot" not in salida.out


# --- Envio (con doble en vez de red) ----------------------------------------

class _Respuesta:
    def __init__(self, status=201):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _peticiones(monkeypatch, respuestas):
    """Doble de urlopen: devuelve o lanza segun `respuestas` y cuenta llamadas."""
    vistas = []

    def falso_urlopen(req, timeout=None):
        vistas.append(req)
        siguiente = respuestas[min(len(vistas) - 1, len(respuestas) - 1)]
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    monkeypatch.setattr(puente.urllib.request, "urlopen", falso_urlopen)
    monkeypatch.setattr(puente.time, "sleep", lambda s: None)   # sin esperas reales
    return vistas


def test_envia_con_token_y_cuerpo_correcto(monkeypatch, tmp_path):
    estados = []
    monkeypatch.setattr(puente, "post_event",
                        lambda *a, **k: estados.append(a) or True)
    salida = tmp_path / "uno.log"
    salida.write_text('{"t_ms":1,"k":1,"mode":"NORMAL","soc":1.0,"relay_a":true,'
                      '"relay_b":true,"relay_c":true,"events":[]}\n', encoding="utf-8")

    assert puente.main(["--file", str(salida), "--url", "http://x/ingest",
                        "--token", "secreto"]) == 0
    url, token, payload = estados[0][:3]
    assert url == "http://x/ingest"
    assert token == "secreto"
    assert payload["mode"] == "NORMAL"


def test_reintenta_tres_veces_y_despues_va_bien(monkeypatch):
    vistas = _peticiones(monkeypatch, [
        urllib.error.URLError("caido"),
        urllib.error.URLError("caido"),
        _Respuesta(201),
    ])
    ok = puente.post_event("http://x/ingest", "secreto", {"mode": "NORMAL", "t_ms": 1},
                           attempts=3, backoff_s=0.0, timeout_s=1.0, echo=lambda m: None)
    assert ok is True
    assert len(vistas) == 3
    # El token viaja en la cabecera Authorization, y solo ahi.
    assert vistas[0].get_header("Authorization") == "Bearer secreto"


def test_falla_tras_los_intentos(monkeypatch):
    vistas = _peticiones(monkeypatch, [urllib.error.URLError("caido")])
    mensajes = []
    ok = puente.post_event("http://x/ingest", "secreto", {"mode": "NORMAL", "t_ms": 1},
                           attempts=3, backoff_s=0.0, timeout_s=1.0, echo=mensajes.append)
    assert ok is False
    assert len(vistas) == 3                      # los 3 intentos
    assert any("fallo tras 3 intentos" in m for m in mensajes)
    assert not any("secreto" in m for m in mensajes)   # el token no se imprime


def test_422_no_se_reintenta(monkeypatch):
    error = urllib.error.HTTPError("http://x/ingest", 422, "invalido", {}, None)
    vistas = _peticiones(monkeypatch, [error])
    assert puente.post_event("http://x/ingest", "t", {"mode": "NORMAL", "t_ms": 1},
                             attempts=3, backoff_s=0.0, timeout_s=1.0,
                             echo=lambda m: None) is False
    assert len(vistas) == 1                      # no insiste con un 422


def test_sin_token_avisa_y_no_envia(capsys, monkeypatch):
    monkeypatch.delenv("INGEST_TOKEN", raising=False)
    assert puente.main(["--file", EVIDENCE]) == 2
    assert "falta el token" in capsys.readouterr().err


def test_todas_las_lineas_de_evidencia_pasan_el_esquema():
    """Los 75 estados del log valido contra el esquema del servidor.

    Une el puente con la ingesta: si el firmware cambia un campo, esta prueba
    (o la de ingesta) lo detecta antes que el dashboard.
    """
    import app

    with open(EVIDENCE, encoding="utf-8", errors="replace") as fh:
        estados = [o for o in (puente.extract_json(l) for l in fh) if o and puente.is_state(o)]
    assert len(estados) == 75
    for o in estados:
        app.State(**o)          # no debe lanzar ValidationError
