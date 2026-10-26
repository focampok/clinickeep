# Deploy the ingest service (Railway)

How to publish `server/` (FastAPI + SQLite + the dashboard) on [Railway](https://railway.app). The service serves the dashboard, the ingest API, and `/calc`.

The static project sheet is a separate publish. It lives in `site/`, and Netlify publishes that directory. It is not this Railway service. This document does not set a Netlify hostname.

## For a judge

Open the read-only demo at [https://clinickeep.focampo.com](https://clinickeep.focampo.com). The Railway backup is [https://clinickeep-production.up.railway.app](https://clinickeep-production.up.railway.app). The sizing calculator is on the same host at `/calc`.

The dashboard stores and shows **simulated** data, and a permanent banner says so. It is not a live feed from a clinic. Do not treat the events on screen as a current clinic report.

## What gets deployed

| Path | What it is |
|---|---|
| `server/app.py` | FastAPI: `POST /ingest`, `GET /api/latest`, `GET /api/events`, `GET /healthz`, the dashboard, and `/calc` |
| `server/requirements.txt` | Dependencies (FastAPI, uvicorn, httpx) |
| `server/Procfile` | `web: uvicorn app:app --host 0.0.0.0 --port $PORT` |
| `server/static/` | `index.html`, the heatmaps and CSVs published with `tools/publish_scenarios.py`, and the calculator from `calc/` published with `tools/publish_calc.py` (served at `/calc`) |

## Steps

### 1. Create the service

1. In Railway: **New Project → Deploy from GitHub repo**, and choose this repo.
2. In **Settings → Source**, set **Root Directory = `server`**.

   This matters. Railway then finds `server/requirements.txt` (to install FastAPI) and the `Procfile` that starts `uvicorn app:app`. If the root stays the repository root, `requirements.txt` is not there and the start fails.

### 2. Environment variables

Under **Variables**, add:

| Variable | Value | Why |
|---|---|---|
| `INGEST_TOKEN` | a long secret token (see below) | authenticates `POST /ingest`; without it, ingest responds 503 |
| `DB_PATH` | `/data/ck.db` | stores the database on the volume (step 3) |
| `ALLOWED_ORIGINS` | optional, empty | CORS: closed by default; only the dashboard's own origin |

Generate the token with either of these. Do not write it into the repo:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
openssl rand -base64 32
```

### 3. Volume (so the database survives redeploys)

1. **New → Volume**, mounted at **`/data`**.
2. Leave `DB_PATH=/data/ck.db` (step 2).

Without a volume the container starts with an empty database on every redeploy. The events are the history, and a lost database cannot be rebuilt from them.

### 4. Domain and health

1. **Settings → Networking → Generate Domain**.
2. Healthcheck (optional): `/healthz`.

### 5. Deploy

With the repo connected, every push deploys. Or use the CLI:

```bash
npm i -g @railway/cli    # or: brew install railway
railway login
railway up --service clinickeep-ingest
```

## Check from the server

Use the domain from step 4. The token stays in the environment, **never** in the repo:

```bash
TOKEN="put-your-INGEST_TOKEN-here"                 # or: export TOKEN="$INGEST_TOKEN"
URL="https://your-service.up.railway.app"

curl -sS "$URL/healthz"

curl -sS -X POST "$URL/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"t_ms":6665,"k":1,"mode":"NORMAL","soc":1.0,"relay_a":true,"relay_b":true,"relay_c":true,"aut_a_h":12.007,"holdover_h":0.534,"safe_h":12.541,"events":[]}'
```

Expected POST response (`201`):

```json
{"ok":true,"id":1,"simulado":true}
```

The public read:

```bash
curl -sS "$URL/api/latest"
curl -sS "$URL/api/events?limit=5"
```

## Expected errors

| Code | When |
|---|---|
| `401` | the `Authorization: Bearer <token>` header is missing, or the token does not match |
| `413` | the body is over 8 KB |
| `422` | the JSON is invalid, or it has extra or missing fields (the schema accepts exactly what the firmware emits) |
| `503` | the service started without `INGEST_TOKEN` set |

## Send firmware or simulator data

Against the deployed service, point the bridge at the public URL:

```bash
INGEST_URL="https://your-service.up.railway.app/ingest" \
INGEST_TOKEN="$TOKEN" \
python3 tools/serial_to_ingest.py --file evidence/wokwi_accept_serial.log
```

Live, reading the Wokwi serial monitor:

```bash
wokwi-cli . --scenario scenario_accept.yaml | \
  INGEST_URL="https://your-service.up.railway.app/ingest" INGEST_TOKEN="$TOKEN" \
  python3 tools/serial_to_ingest.py
```

## Run it locally

```bash
cd server
cp .env.example .env          # .env is in .gitignore: it is not committed
export $(grep -v '^#' .env | xargs)
uvicorn app:app --host 0.0.0.0 --port $PORT   # the same command as the Procfile
```

The dashboard at `http://127.0.0.1:$PORT/` shows the live state of whatever the bridge is posting.

## Security notes

- The token travels only in the `Authorization` header. Neither the service nor the bridge prints it in a log.
- The read routes (`/api/*`, `/healthz`, and the dashboard) are **public on purpose** at this stage. They only read.
- Rotating the token means changing the variable on Railway (that redeploys) and updating `INGEST_TOKEN` wherever the bridge runs.
- `.env`, `server/data/`, and `*.db` are in `.gitignore`.
