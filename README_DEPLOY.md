# Despliegue del servicio de ingesta (Railway)

Cómo publicar `server/` (FastAPI + SQLite + dashboard) en
[Railway](https://railway.app). El servicio sirve el dashboard y la ingesta:
nada más hace falta.

> Recordatorio: los datos que guarda y muestra son **simulados**. El dashboard
> lo declara en un banner permanente.

## Qué se despliega

| Ruta | Qué es |
|---|---|
| `server/app.py` | FastAPI: `POST /ingest`, `GET /api/latest`, `GET /api/events`, `GET /healthz`, dashboard |
| `server/requirements.txt` | Dependencias (FastAPI, uvicorn, httpx) |
| `server/Procfile` | `web: uvicorn app:app --host 0.0.0.0 --port $PORT` |
| `server/static/` | `index.html`, mapas y CSV publicados con `tools/publish_scenarios.py` |

## Pasos

### 1. Crear el servicio

1. En Railway: **New Project → Deploy from GitHub repo** y elige este repo.
2. En **Settings → Source**, pon **Root Directory = `server`**.

   Es importante: así Railway encuentra `server/requirements.txt` (para instalar
   FastAPI) y el `Procfile` que arranca `uvicorn app:app`. Si dejas la raíz del
   repo, `requirements.txt` no está en la raíz y el arranque falla.

### 2. Variables de entorno

En **Variables**, añade:

| Variable | Valor | Por qué |
|---|---|---|
| `INGEST_TOKEN` | un token largo y secreto (ver abajo) | autentica `POST /ingest`; sin él la ingesta responde 503 |
| `DB_PATH` | `/data/ck.db` | guarda la base en el volumen (ver paso 3) |
| `ALLOWED_ORIGINS` | (opcional, vacío) | CORS: por defecto cerrado; solo el propio origen del dashboard |

Genera el token con cualquiera de estas (no lo escribas en el repo):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
openssl rand -base64 32
```

### 3. Volumen (para que la base sobreviva a los redeploys)

1. **New → Volume** y móntalo en **`/data`**.
2. Deja `DB_PATH=/data/ck.db` (paso 2).

Sin volumen, el contenedor arranca con la base vacía en cada redeploy: los
eventos son históricos y no se puede recuperar lo perdido.

### 4. Dominio y salud

1. **Settings → Networking → Generate Domain**.
2. Healthcheck (opcional): `/healthz`.

### 5. Desplegar

Con el repo conectado, cada push despliega. Alternativa con la CLI:

```bash
npm i -g @railway/cli    # o: brew install railway
railway login
railway up --service clinickeep-ingest
```

## Prueba desde el servidor

Con el dominio del paso 4. El token va en el entorno, **nunca** en el repo:

```bash
TOKEN="pon-aqui-tu-INGEST_TOKEN"                 # o: export TOKEN="$INGEST_TOKEN"
URL="https://tu-servicio.up.railway.app"

curl -sS "$URL/healthz"

curl -sS -X POST "$URL/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"t_ms":6665,"k":1,"mode":"NORMAL","soc":1.0,"relay_a":true,"relay_b":true,"relay_c":true,"aut_a_h":12.007,"holdover_h":0.534,"safe_h":12.541,"events":[]}'
```

Respuesta esperada del POST (`201`):

```json
{"ok":true,"id":1,"simulado":true}
```

Y el estado, en la lectura pública:

```bash
curl -sS "$URL/api/latest"
curl -sS "$URL/api/events?limit=5"
```

## Errores esperados

| Código | Cuándo |
|---|---|
| `401` | falta el header `Authorization: Bearer <token>` o el token no coincide |
| `413` | el cuerpo pasa de 8 KB |
| `422` | el JSON no es válido, o trae campos de más / de menos (el esquema acepta exactamente lo que emite el firmware) |
| `503` | el servicio arrancó sin `INGEST_TOKEN` configurado |

## Enviar datos del firmware real o simulado

Contra el servicio desplegado, el puente apunta a la URL pública:

```bash
INGEST_URL="https://tu-servicio.up.railway.app/ingest" \
INGEST_TOKEN="$TOKEN" \
python3 tools/serial_to_ingest.py --file evidence/wokwi_accept_serial.log
```

Y en vivo, leyendo el monitor serie de Wokwi:

```bash
wokwi-cli . --scenario scenario_accept.yaml | \
  INGEST_URL="https://tu-servicio.up.railway.app/ingest" INGEST_TOKEN="$TOKEN" \
  python3 tools/serial_to_ingest.py
```

## En local

```bash
cd server
cp .env.example .env          # .env está en .gitignore: no se sube
export $(grep -v '^#' .env | xargs)
uvicorn app:app --host 0.0.0.0 --port $PORT   # el mismo comando del Procfile
```

En el dashboard (`http://127.0.0.1:$PORT/`) se ve el estado en vivo de lo que
vaya entrando por el puente.

## Notas de seguridad

- El token solo viaja en el header `Authorization`; ni el servicio ni el
  puente lo imprimen en ningún log.
- Las rutas de lectura (`/api/*`, `/healthz`, el dashboard) son **públicas a
  propósito** en esta fase: solo leen, no escriben.
- Rotar el token = cambiar la variable en Railway (redeploy automático) y
  actualizar `INGEST_TOKEN` donde corra el puente.
- `.env`, `server/data/` y `*.db` están en `.gitignore`.
