# Notifier — Google Form → Telegram Webhook

A small FastAPI service that receives Google Form submissions (via
HMAC-signed webhook) and forwards them to a Telegram forum topic.

**Production deployment:** systemd + nginx + Python venv (no Docker).
Docker images are provided as an alternative but are not the default path.

**Domain:** `pb.kotakpasir.my.id` (webhook at `/webhook/form`, health at `/healthz`)

Phase 2 will add tools to manage the Telegram group (topics, members,
messages, settings, auto-reply) — the service stubs are already in place.

## Architecture

```
┌──────────────┐   onFormSubmit    ┌──────────────────┐
│ Google Form  │ ────────────────► │ sendTele_v2.gs   │
└──────────────┘   (GAS trigger)   │ (HMAC sign + POST)│
                                   └────────┬─────────┘
                                            │ HTTPS
                                            │ X-Signature: <hex>
                                            ▼
                                   ┌──────────────────┐
                                   │ Cloudflare (TLS) │
                                   └────────┬─────────┘
                                            │ Origin CA cert
                                            ▼
                                   ┌──────────────────┐
                                   │ nginx (443)      │
                                   └────────┬─────────┘
                                            │ proxy_pass
                                            ▼
                                   ┌──────────────────┐
                                   │ FastAPI (8000)   │
                                   │  POST /webhook/  │
                                   │  GET  /healthz   │
                                   └────────┬─────────┘
                                            │ httpx
                                            ▼
                                   ┌──────────────────┐
                                   │ Telegram Bot API │
                                   │ (forum topic)    │
                                   └──────────────────┘
```

## Setup

### 1. Gather Telegram config (you likely have this already)
- **Bot token** — from BotFather, or copy from your existing GAS Script Properties
- **Chat ID** — from `https://api.telegram.org/bot<token>/getUpdates` (look for `"chat":{"id":-100...}`)
- **Thread ID** — the forum topic's `message_thread_id` (integer, e.g. `25`)

If you already have these in your existing GAS, just reuse them.

### 2. Generate a fresh `WEBHOOK_SECRET`
```bash
openssl rand -hex 32
```
This is the HMAC key for the webhook. Must match what's set in GAS Script Properties.

### 3. Get a Cloudflare Origin CA cert
Domain `pb.kotakpasir.my.id` is already behind Cloudflare.

In Cloudflare dashboard: **SSL/TLS → Origin Server → Create Certificate**
- Hostname: `pb.kotakpasir.my.id` (and optionally `*.kotakpasir.my.id` for future)
- Save cert to VPS: `/etc/ssl/certs/cloudflare-origin.pem`
- Save private key to VPS: `/etc/ssl/private/cloudflare-origin.key`
- Cert is valid **15 years** — no renewal needed

### 4. Install the notifier service on the VPS

```bash
# Create service user
sudo useradd -r -s /usr/sbin/nologin --home-dir /opt/prakombot notifier

# Deploy code
sudo mkdir -p /opt/prakombot
sudo chown -R notifier:notifier /opt/prakombot
git clone https://github.com/camagenta/prakombot.git /opt/prakombot
cd /opt/prakombot
python3 -m venv .venv
.venv/bin/pip install -r notifier/requirements.txt

# Write env file (interactive — generates fresh WEBHOOK_SECRET)
sudo ./notifier/deploy/setup-prod.sh
```

### 5. Install nginx + systemd

```bash
# nginx
sudo cp notifier/deploy/nginx.conf /etc/nginx/sites-available/notifier
sudo ln -s /etc/nginx/sites-available/notifier /etc/nginx/sites-enabled/notifier
sudo nginx -t && sudo systemctl reload nginx

# systemd
sudo cp notifier/deploy/form-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now form-bot
sudo systemctl status form-bot
```

### 6. Install the GAS trigger

1. Open your Google Form → **Extensions → Apps Script**
2. Paste the contents of `notifier/gas/sendTele_v2.gs` (replace any old `sendTele.gs`)
3. In **Project Settings → Script Properties**, add:
   - `WEBHOOK_URL` = `https://pb.kotakpasir.my.id/webhook/form`
   - `WEBHOOK_SECRET` = the value `setup-prod.sh` printed at the end
4. Run `installTrigger` once (authorize when prompted)
5. Submit a test response to verify the topic message arrives

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | — | Bot token from BotFather |
| `TELEGRAM_CHAT_ID` | yes | — | Supergroup chat ID (negative number) |
| `TELEGRAM_THREAD_ID` | no | `0` | Forum topic to post into |
| `TELEGRAM_PARSE_MODE` | no | `HTML` | `HTML` or `MarkdownV2` |
| `TELEGRAM_MAX_RETRIES` | no | `3` | Retries on 429/5xx |
| `TELEGRAM_RETRY_BASE_SECONDS` | no | `1.0` | Exponential backoff base |
| `TELEGRAM_API_BASE` | no | `https://api.telegram.org` | Override for testing |
| `WEBHOOK_SECRET` | yes | — | HMAC shared secret (32+ hex chars) |
| `WEBHOOK_HOST` | no | `127.0.0.1` | Bind address |
| `WEBHOOK_PORT` | no | `8000` | Bind port |

## API

### `GET /healthz`
Returns `{"status": "ok"}` — used by Cloudflare health checks and Docker healthcheck.

### `POST /webhook/form`
Receives a form submission.

**Headers**:
- `X-Signature: <hex sha256 hmac of raw body, using WEBHOOK_SECRET>`
- `Content-Type: application/json`

**Body**:
```json
{
  "form_id": "1AbC...XYZ",
  "submitted_at": "2025-01-15T10:30:00Z",
  "responses": [
    {"index": 0, "title": "Nama", "answer": "Budi"},
    {"index": 1, "title": "NIP", "answer": "12345"}
  ]
}
```

**Responses**:
- `200 OK` — `{"ok": true, "message_id": 99}`
- `401 Unauthorized` — bad or missing signature
- `422 Unprocessable Entity` — malformed JSON or missing fields
- `500 Internal Server Error` — Telegram API failed (after retries)

## Smoke test

After deploy:
```bash
# Health (no auth)
curl -fsS https://pb.kotakpasir.my.id/healthz
# {"status":"ok"}

# Webhook with valid signature
BODY='{"form_id":"test","submitted_at":"2025-01-15T10:30:00Z","responses":[{"index":0,"title":"Nama","answer":"Budi"}]}'
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $2}')
curl -fsS -X POST https://pb.kotakpasir.my.id/webhook/form \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIG" \
  --data "$BODY"
# {"ok":true,"message_id":99}
```

## Development

```bash
# Run tests (from repo root)
python3 -m unittest discover -s notifier/tests -p "test_*.py" -v

# Run locally
TELEGRAM_BOT_TOKEN=... WEBHOOK_SECRET=... python3 -m notifier.main
```

## Project Structure

```
notifier/
├── __init__.py
├── app.py                  # FastAPI app factory
├── main.py                 # uvicorn entrypoint
├── config.py               # Env singleton (with _int_env safety)
├── auth.py                 # HMAC verify
├── schemas.py              # pydantic models
├── requirements.txt
├── README.md
├── routes/
│   ├── __init__.py
│   ├── webhook.py          # POST /webhook/form
│   └── health.py           # GET /healthz
├── services/
│   ├── __init__.py
│   ├── telegram.py         # httpx client + retry
│   ├── topics.py           # Phase 2 stub
│   ├── messages.py         # Phase 2 stub
│   ├── members.py          # Phase 2 stub
│   ├── autoreply.py        # Phase 2 stub
│   └── settings.py         # Phase 2 stub
├── gas/
│   └── sendTele_v2.gs      # Google Apps Script
├── deploy/
│   ├── nginx.conf
│   ├── form-bot.service
│   ├── Dockerfile
│   └── docker-compose.yml
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_config.py
    ├── test_auth.py
    ├── test_schemas.py
    ├── test_telegram.py
    └── test_webhook.py
```

## Phase 2 (future)

The `services/{topics,messages,members,autoreply,settings}.py` modules
contain `Protocol` interfaces and `NotImplementedError` stubs. Phase 2
swaps in real implementations without changing the route layer.
