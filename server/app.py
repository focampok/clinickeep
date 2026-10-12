"""app.py - Ingesta HTTP + dashboard de ClinicKeep (Fase 3).

Servicio FastAPI de un solo archivo:

  POST /ingest        recibe un estado del firmware (JSON) y lo guarda
  GET  /api/latest    ultimo estado guardado
  GET  /api/events    ultimos N eventos (?limit=200)
  GET  /healthz       salud + cuantos eventos hay
  GET  /              dashboard (server/static/index.html)
  GET  /static/*      imagenes y CSV publicados por tools/publish_scenarios.py

El esquema aceptado es EXACTAMENTE lo que emite wokwi/main.py en emit_json()
(campos reales del firmware); cualquier campo de mas se rechaza. Ver
docs/INGEST_SCHEMA.md para el mapeo campo -> origen.

Variables de entorno:
  INGEST_TOKEN    token que debe venir en "Authorization: Bearer <token>".
                  Si esta vacio, /ingest responde 503 (no se acepta nada).
  DB_PATH         ruta de la base SQLite (por defecto ./data/ck.db).
  ALLOWED_ORIGINS origenes permitidos para CORS, separados por coma.
                  Por defecto vacio: solo el propio origen (cerrado).

Todos los datos de esta fase son SIMULADOS: cada evento se guarda con
"simulado": true y el dashboard lo declara de forma permanente.
"""

import hmac
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# --- Constantes de la fase ---------------------------------------------------

MAX_BODY_BYTES = 8 * 1024      # 8 KB
MAX_EVENTS = 5000              # retencion: solo los ultimos 5000
DEFAULT_DB_PATH = os.path.join("data", "ck.db")
DEFAULT_EVENTS_LIMIT = 200
MAX_EVENTS_LIMIT = 1000
MODES = ("NORMAL", "CORTE", "AHORRO", "CRITICO", "RESTAURACION", "FALLO_SENSOR")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

_lock = threading.Lock()


# --- Esquema del estado del firmware ----------------------------------------
# Campos reales que emite wokwi/main.py:emit_json(). Si el firmware cambia,
# este modelo es el unico punto que hay que tocar en la ingesta.

class State(BaseModel):
    model_config = ConfigDict(extra="forbid")   # rechaza campos no esperados

    t_ms: int = Field(ge=0)
    k: float = Field(gt=0)
    mode: str
    soc: float = Field(ge=0.0, le=1.0)
    relay_a: bool
    relay_b: bool
    relay_c: bool
    aut_a_h: float | None = None
    holdover_h: float | None = None
    safe_h: float | None = None
    events: list[str] = Field(default_factory=list)

    # Fase 3b: el firmware nuevo tambien emite estos. Todos son opcionales
    # (default None), asi que un evento antiguo de 11 campos sigue validando
    # igual y el dashboard cae a su derivacion cuando llegan como None.
    grid_ok: bool | None = None
    alarm: bool | None = None
    aut_total_h: float | None = None
    temp_c: float | None = None
    temp_ok: bool | None = None

    @field_validator("mode")
    @classmethod
    def _mode_conocido(cls, v):
        if v not in MODES:
            raise ValueError("modo desconocido: %r (esperado: %s)" % (v, ", ".join(MODES)))
        return v

    @field_validator("events")
    @classmethod
    def _events_limitados(cls, v):
        if len(v) > 50:
            raise ValueError("demasiados eventos en un solo estado (max 50)")
        return v


# --- Configuracion leida en cada peticion (facilita las pruebas) -------------

def _db_path():
    return os.environ.get("DB_PATH") or DEFAULT_DB_PATH


def _ingest_token():
    return os.environ.get("INGEST_TOKEN") or ""


def _allowed_origins():
    raw = os.environ.get("ALLOWED_ORIGINS") or ""
    return [o.strip() for o in raw.split(",") if o.strip()]


def _connect():
    path = _db_path()
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


# Columnas que anadio la Fase 3b, para poder migrar bases ya existentes
# (incluida la del volumen de Railway) sin perder los eventos guardados.
COLUMNAS_3B = (
    ("grid_ok", "INTEGER"),
    ("alarm", "INTEGER"),
    ("aut_total_h", "REAL"),
    ("temp_c", "REAL"),
    ("temp_ok", "INTEGER"),
)


def _migrar(conn):
    actuales = {fila["name"] for fila in conn.execute("PRAGMA table_info(events)")}
    for nombre, tipo in COLUMNAS_3B:
        if nombre not in actuales:
            # nombre y tipo son constantes de este modulo, no entrada externa
            conn.execute("ALTER TABLE events ADD COLUMN %s %s" % (nombre, tipo))


def init_db():
    with _lock:
        conn = _connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_server   TEXT    NOT NULL,   -- ISO 8601 UTC del servidor
                    simulado    INTEGER NOT NULL,   -- siempre 1 en esta fase
                    t_ms        INTEGER NOT NULL,
                    k           REAL    NOT NULL,
                    mode        TEXT    NOT NULL,
                    soc         REAL    NOT NULL,
                    relay_a     INTEGER NOT NULL,
                    relay_b     INTEGER NOT NULL,
                    relay_c     INTEGER NOT NULL,
                    aut_a_h     REAL,
                    holdover_h  REAL,
                    safe_h      REAL,
                    events      TEXT    NOT NULL,
                    raw         TEXT    NOT NULL,
                    grid_ok     INTEGER,
                    alarm       INTEGER,
                    aut_total_h REAL,
                    temp_c      REAL,
                    temp_ok     INTEGER
                )
                """
            )
            _migrar(conn)
            conn.commit()
        finally:
            conn.close()


def _row_to_event(row):
    def opt_bool(valor):
        return None if valor is None else bool(valor)

    return {
        "id": row["id"],
        "ts_server": row["ts_server"],
        "simulado": bool(row["simulado"]),
        "t_ms": row["t_ms"],
        "k": row["k"],
        "mode": row["mode"],
        "soc": row["soc"],
        "relay_a": bool(row["relay_a"]),
        "relay_b": bool(row["relay_b"]),
        "relay_c": bool(row["relay_c"]),
        "aut_a_h": row["aut_a_h"],
        "holdover_h": row["holdover_h"],
        "safe_h": row["safe_h"],
        "events": json.loads(row["events"]),
        # Fase 3b: None en los eventos guardados antes de estos campos.
        "grid_ok": opt_bool(row["grid_ok"]),
        "alarm": opt_bool(row["alarm"]),
        "aut_total_h": row["aut_total_h"],
        "temp_c": row["temp_c"],
        "temp_ok": opt_bool(row["temp_ok"]),
    }


def _opt_int(valor):
    """None se guarda como NULL; True/False como 1/0."""
    return None if valor is None else int(valor)


def store_event(state: State):
    """Guarda un estado con la marca de tiempo del servidor y poda la retencion."""
    ts_server = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    raw = state.model_dump_json()
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO events (ts_server, simulado, t_ms, k, mode, soc,
                                    relay_a, relay_b, relay_c, aut_a_h,
                                    holdover_h, safe_h, events, raw,
                                    grid_ok, alarm, aut_total_h, temp_c, temp_ok)
                VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts_server, state.t_ms, state.k, state.mode, state.soc,
                    int(state.relay_a), int(state.relay_b), int(state.relay_c),
                    state.aut_a_h, state.holdover_h, state.safe_h,
                    json.dumps(state.events), raw,
                    _opt_int(state.grid_ok), _opt_int(state.alarm),
                    state.aut_total_h, state.temp_c, _opt_int(state.temp_ok),
                ),
            )
            # Retencion: dejar solo los ultimos MAX_EVENTS por id.
            conn.execute(
                "DELETE FROM events WHERE id <= (SELECT MAX(id) FROM events) - ?",
                (MAX_EVENTS,),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


# --- Aplicacion -------------------------------------------------------------

app = FastAPI(
    title="ClinicKeep ingest",
    description="Ingesta y dashboard de datos SIMULADOS de ClinicKeep.",
    version="3.0.0",
)


@app.middleware("http")
async def cors_propio(request: Request, call_next):
    """CORS cerrado: solo los origenes de ALLOWED_ORIGINS (por defecto, ninguno).

    Mismo origen (el dashboard servido por esta app) no necesita CORS.
    Nunca se registra ni se devuelve el token.
    """
    response = await call_next(request)
    origin = request.headers.get("origin")
    if origin and origin in _allowed_origins():
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def _errores(exc):
    """Errores de Pydantic en JSON puro (ctx puede traer un ValueError crudo)."""
    limpios = []
    for err in exc.errors(include_url=False, include_input=False):
        err.pop("ctx", None)
        limpios.append(err)
    return limpios


def _check_auth(request: Request):
    """401 si falta el token o no coincide (comparacion en tiempo constante)."""
    expected = _ingest_token()
    if not expected:
        raise HTTPException(status_code=503, detail="ingesta no configurada (falta INGEST_TOKEN)")
    header = request.headers.get("authorization") or ""
    scheme, _, provided = header.partition(" ")
    if scheme.lower() != "bearer" or not provided:
        raise HTTPException(status_code=401, detail="falta el token Bearer")
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="token invalido")


@app.post("/ingest")
async def ingest(request: Request):
    # 1. Autenticacion (401)
    _check_auth(request)

    # 2. Tamano (413): primero por cabecera, despues contando los bytes reales.
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > MAX_BODY_BYTES:
                raise HTTPException(status_code=413, detail="cuerpo mayor de 8 KB")
        except ValueError:
            raise HTTPException(status_code=422, detail="Content-Length invalido")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="cuerpo mayor de 8 KB")

    # 3. Validacion (422)
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=422, detail="JSON invalido")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="se esperaba un objeto JSON")
    try:
        state = State(**payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_errores(exc))

    event_id = store_event(state)
    return JSONResponse(
        {"ok": True, "id": event_id, "simulado": True},
        status_code=201,
    )


@app.get("/api/latest")
def api_latest():
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT 1").fetchone()
            total = conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
        finally:
            conn.close()
    return {"event": None if row is None else _row_to_event(row), "count": total}


@app.get("/api/events")
def api_events(limit: int = DEFAULT_EVENTS_LIMIT):
    limit = max(1, min(int(limit), MAX_EVENTS_LIMIT))
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
        finally:
            conn.close()
    # Orden cronologico ascendente: mas facil de pintar en la linea de tiempo.
    return {"events": [_row_to_event(r) for r in reversed(rows)], "count": total}


@app.get("/healthz")
def healthz():
    with _lock:
        conn = _connect()
        try:
            total = conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
        finally:
            conn.close()
    return {
        "status": "ok",
        "events": total,
        "db_path": _db_path(),
        "simulado": True,
    }


@app.get("/")
def dashboard():
    index = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index):
        raise HTTPException(status_code=404, detail="dashboard no encontrado")
    return FileResponse(index, media_type="text/html")


if os.path.isdir(STATIC_DIR):
    # static/img/*.png y static/csv/*.csv los publica tools/publish_scenarios.py
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# La calculadora de dimensionamiento (Fase 4) la publica tools/publish_calc.py,
# que copia calc/ aqui dentro (asi server/ sigue siendo autocontenido). Va
# montada en /calc, y no bajo /static, para que la pagina pueda pedir su calc.js
# con una ruta relativa. html=True sirve index.html en /calc.
CALC_DIR = os.path.join(STATIC_DIR, "calc")
if os.path.isdir(CALC_DIR):
    app.mount("/calc", StaticFiles(directory=CALC_DIR, html=True), name="calc")

init_db()
