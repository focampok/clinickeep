"""Pruebas del puente tools/serial_to_ingest.py.

Sin red real: o se usa --dry-run, o se sustituye urllib.request.urlopen por un
doble que cuenta llamadas y devuelve lo que haga falta.

Los logs congelados (viejo de 11 campos y nuevo de 16) viven en server/tests/data,
asi que estas pruebas no dependen de evidence/. Las que si lo usan se saltan si
falta: server/ tiene que poder probarse por si solo.
"""

import io
import json
import urllib.error

import pytest

from conftest import EVIDENCE, LOG_NUEVO, LOG_VIEJO, saltar_si_falta

puente = pytest.importorskip("serial_to_ingest")

# Firmware de la Fase 3 -> Fase 3b: 11 campos -> 16.
CAMPOS_VIEJOS = 11
CAMPOS_NUEVOS = 16
ESTADOS_LOG_VIEJO = 75          # el log congelado del firmware viejo


def _estados_de(ruta):
    """Estados que el puente deberia reenviar de un log."""
    with open(ruta, encoding="utf-8", errors="replace") as fh:
        return [o for o in (puente.extract_json(l) for l in fh) if o and puente.is_state(o)]


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


# --- Los dos formatos, de punta a punta --------------------------------------

@pytest.mark.parametrize("ruta,campos", [
    (LOG_VIEJO, CAMPOS_VIEJOS),
    (LOG_NUEVO, CAMPOS_NUEVOS),
])
def test_log_congelado_valida_y_pasa_el_esquema(ruta, campos):
    """Ambos formatos pasan el filtro del puente y el esquema del servidor."""
    saltar_si_falta(ruta)
    import app

    estados = _estados_de(ruta)
    assert estados, "el log no tiene estados"
    for o in estados:
        assert len(o) == campos, sorted(o)
        app.State(**o)                       # no debe lanzar ValidationError

    if campos == CAMPOS_VIEJOS:
        assert len(estados) == ESTADOS_LOG_VIEJO
        # El formato viejo no trae los campos de la Fase 3b.
        assert not any("temp_c" in o or "grid_ok" in o for o in estados)
    else:
        # El formato nuevo los trae todos, siempre.
        for o in estados:
            assert all(c in o for c in ("grid_ok", "alarm", "aut_total_h", "temp_c", "temp_ok"))


def test_el_log_viejo_sigue_funcionando_por_el_puente(capsys, tmp_path):
    """El log del firmware viejo se reenvia igual: 75 estados y nada de boot/cmd."""
    saltar_si_falta(LOG_VIEJO)
    assert puente.main(["--file", LOG_VIEJO, "--dry-run"]) == 0
    salida = capsys.readouterr()

    lineas = [l for l in salida.out.splitlines() if l.strip()]
    assert len(lineas) == ESTADOS_LOG_VIEJO
    objetos = [json.loads(l) for l in lineas]
    assert all("mode" in o and "t_ms" in o for o in objetos)
    assert all(o.get("cmd") is None and o.get("boot") is None for o in objetos)
    assert all("temp_c" not in o for o in objetos)      # es el formato viejo
    assert "estados %d | enviados %d | fallidos 0" % (ESTADOS_LOG_VIEJO, ESTADOS_LOG_VIEJO) in salida.err


def test_el_log_nuevo_pasa_por_el_puente(capsys):
    """El log regenerado con el firmware nuevo: reenvia todo, con los 16 campos."""
    saltar_si_falta(LOG_NUEVO)
    esperados = _estados_de(LOG_NUEVO)
    assert puente.main(["--file", LOG_NUEVO, "--dry-run"]) == 0
    salida = capsys.readouterr()

    lineas = [l for l in salida.out.splitlines() if l.strip()]
    assert len(lineas) == len(esperados)
    objetos = [json.loads(l) for l in lineas]
    assert all("temp_c" in o and "grid_ok" in o and "alarm" in o for o in objetos)
    assert any(o["temp_c"] is not None for o in objetos)      # hubo lecturas validas
    assert "estados %d | enviados %d | fallidos 0" % (len(esperados), len(esperados)) in salida.err


def test_dry_run_con_el_log_vivo_de_evidence(capsys):
    """El log que usa el repo entero (evidence/) tambien pasa, sea cual sea su formato."""
    saltar_si_falta(EVIDENCE)
    esperados = _estados_de(EVIDENCE)
    assert len(esperados) >= 50

    assert puente.main(["--file", EVIDENCE, "--dry-run"]) == 0
    salida = capsys.readouterr()
    lineas = [l for l in salida.out.splitlines() if l.strip()]
    assert len(lineas) == len(esperados)
    assert "no se envia nada" in salida.err

    import app
    for o in esperados:
        app.State(**o)
    # Si el log ya es del firmware nuevo, todos los estados traen los 5 campos.
    if any("grid_ok" in o for o in esperados):
        assert all("grid_ok" in o for o in esperados)


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
        '{"t_ms":2,"k":1,"mode":"CORTE","grid_ok":false,"alarm":false,"soc":0.5,'
        '"relay_a":true,"relay_b":true,"relay_c":false,"aut_a_h":6.0,"aut_total_h":9.0,'
        '"holdover_h":0.5,"safe_h":6.5,"temp_c":25.0,"temp_ok":true,"events":["shed_c"]}\n'
        'linea suelta sin json\n',
        encoding="utf-8")
    assert puente.main(["--file", str(mezcla), "--dry-run"]) == 0
    salida = capsys.readouterr()
    assert len([l for l in salida.out.splitlines() if l.strip()]) == 2
    assert "estados 2 | enviados 2 | fallidos 0 | lineas ignoradas 6" in salida.err
    assert '"grid_ok": false' in salida.out          # el nuevo conserva sus campos


def test_dry_run_desde_stdin(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(
        '{"boot_ready":true}\n'
        '{"t_ms":9,"k":1,"mode":"CORTE","grid_ok":false,"alarm":false,"soc":0.5,'
        '"relay_a":true,"relay_b":true,"relay_c":false,"aut_a_h":6.0,"aut_total_h":9.0,'
        '"holdover_h":0.5,"safe_h":6.5,"temp_c":25.0,"temp_ok":true,"events":[]}\n'))
    assert puente.main(["--dry-run"]) == 0
    salida = capsys.readouterr()
    assert '"mode": "CORTE"' in salida.out
    assert '"temp_c": 25.0' in salida.out
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
    saltar_si_falta(LOG_VIEJO)
    assert puente.main(["--file", LOG_VIEJO]) == 2
    assert "falta el token" in capsys.readouterr().err
