#!/usr/bin/env python3
"""serial_to_ingest.py - puente del monitor serie de Wokwi a la ingesta HTTP.

Lee lineas del monitor serie (stdin o --file), se queda con las lineas de
ESTADO y las reenvia a POST /ingest. Solo usa la libreria estandar.

Uso tipico:

    wokwi-cli . --scenario scenario_accept.yaml | python3 tools/serial_to_ingest.py

Repetir una corrida ya guardada (no necesita red real si se usa --dry-run):

    python3 tools/serial_to_ingest.py --file evidence/wokwi_accept_serial.log --dry-run
    INGEST_URL=http://127.0.0.1:8000/ingest INGEST_TOKEN=... \\
        python3 tools/serial_to_ingest.py --file evidence/wokwi_accept_serial.log

Que se reenvia: los objetos JSON que son ESTADOS, es decir los que traen
"mode" y "t_ms" (los que emite emit_json() en wokwi/main.py). Se descartan:

  * lineas que no son JSON (ruido del arranque del ESP32, logs de wokwi-cli);
  * {"boot": ...} y {"boot_ready": ...} (ventana de arranque seguro);
  * {"cmd": ...} (eco de comandos GRID0/GRID1/GRID/K=N).

Reintentos: hasta 3 intentos por evento, con espera creciente entre ellos.
Con --dry-run no se envia nada: se imprime lo que se enviaria.

Variables de entorno: INGEST_URL (por defecto http://127.0.0.1:8000/ingest),
INGEST_TOKEN (token Bearer). El token nunca se imprime.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8000/ingest"
DEFAULT_ATTEMPTS = 3
DEFAULT_BACKOFF_S = 1.0
DEFAULT_TIMEOUT_S = 5.0

# Claves que marcan lineas que NO son estados.
NON_STATE_KEYS = ("boot", "boot_ready", "cmd")


def extract_json(line):
    """Devuelve el objeto JSON de la linea, o None si no hay ninguno.

    Tolera prefijos (por ejemplo un prompt) buscando el primer '{'.
    """
    line = line.strip()
    if not line:
        return None
    for start in (0, line.find("{")):
        if start < 0:
            continue
        try:
            obj = json.loads(line[start:])
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(obj, dict):
            return obj
    return None


def is_state(obj):
    """True solo para los estados que emite el firmware (no boot, no comandos)."""
    if any(k in obj for k in NON_STATE_KEYS):
        return False
    return "mode" in obj and "t_ms" in obj


def post_event(url, token, payload, attempts, backoff_s, timeout_s, echo):
    """Envia un evento con reintentos. Devuelve True si el servidor lo acepto."""
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,   # nunca se imprime
    }
    last_error = None
    for intento in range(1, attempts + 1):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                if 200 <= resp.status < 300:
                    return True
                last_error = "HTTP %d" % resp.status
        except urllib.error.HTTPError as exc:
            last_error = "HTTP %d" % exc.code
            # 401/413/422 no mejoran reintentando: es un fallo del puente o del dato.
            if exc.code in (401, 403, 413, 422):
                echo("  ! %s (no se reintenta)" % last_error)
                return False
        except (urllib.error.URLError, OSError) as exc:
            last_error = str(exc)
        if intento < attempts:
            time.sleep(backoff_s * intento)
    echo("  ! fallo tras %d intentos: %s" % (attempts, last_error))
    return False


def iter_lines(path):
    if path is None:
        for line in sys.stdin:
            yield line
    else:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                yield line


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Reenvia los estados del monitor serie de Wokwi a POST /ingest.")
    ap.add_argument("--file", help="leer de este archivo en vez de stdin")
    ap.add_argument("--url", default=os.environ.get("INGEST_URL") or DEFAULT_URL,
                    help="URL de ingesta (por defecto: $INGEST_URL o %s)" % DEFAULT_URL)
    ap.add_argument("--token", default=os.environ.get("INGEST_TOKEN") or "",
                    help="token Bearer (por defecto: $INGEST_TOKEN)")
    ap.add_argument("--dry-run", action="store_true",
                    help="imprimir en vez de enviar")
    ap.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS,
                    help="intentos por evento, con espera creciente (por defecto: %d)"
                         % DEFAULT_ATTEMPTS)
    ap.add_argument("--backoff", type=float, default=DEFAULT_BACKOFF_S,
                    help="segundos base de la espera entre intentos (por defecto: %.1f)"
                         % DEFAULT_BACKOFF_S)
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S,
                    help="timeout por peticion en segundos (por defecto: %.1f)"
                         % DEFAULT_TIMEOUT_S)
    args = ap.parse_args(argv)

    def echo(msg):
        print(msg, file=sys.stderr, flush=True)

    if not args.dry_run and not args.token:
        echo("falta el token: exporta INGEST_TOKEN o pasa --token (usa --dry-run para no enviar)")
        return 2

    if args.dry_run:
        echo("[dry-run] destino %s (no se envia nada)" % args.url)
    else:
        echo("enviando a %s" % args.url)

    estados = enviados = fallidos = ignoradas = 0
    for line in iter_lines(args.file):
        obj = extract_json(line)
        if obj is None or not is_state(obj):
            ignoradas += 1
            continue
        estados += 1
        if args.dry_run:
            print(json.dumps(obj, sort_keys=True), flush=True)
            enviados += 1
            continue
        if post_event(args.url, args.token, obj, args.attempts, args.backoff,
                      args.timeout, echo):
            enviados += 1
        else:
            fallidos += 1

    echo("estados %d | enviados %d | fallidos %d | lineas ignoradas %d"
         % (estados, enviados, fallidos, ignoradas))
    return 1 if fallidos else 0


if __name__ == "__main__":
    sys.exit(main())
