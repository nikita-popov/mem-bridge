# mem-bridge

Lightweight HTTP bridge that exposes a local [MemPalace](https://github.com/MemPalace/mempalace)
instance as a REST API. Designed to run under a dedicated `chatd` system user on Debian,
behind an nginx reverse proxy, and to be wired into Perplexity as a custom remote connector.

## Stack

- **FastAPI** – request handling
- **Gunicorn + gevent** – production server (single worker, async I/O)
- **pydantic-settings** – configuration via env vars / `.env`
- **MemPalace CLI** – invoked as subprocess; `--palace` path is explicit

## Directory layout (server)

```
/opt/chatd/
├── venv/                      # shared virtualenv
├── mem-bridge/                # this repo (git clone here)
├── .mempalace/palace/         # MemPalace data directory
└── etc/
    └── mempalace.tokens       # bearer tokens, one per line, mode 600
```

## Configuration

All settings can be overridden via environment variables prefixed with `MEMBRIDGE_`:

| Variable | Default | Description |
|---|---|---|
| `MEMBRIDGE_PALACE_PATH` | `/opt/chatd/.mempalace/palace` | Path passed to `mempalace --palace` |
| `MEMBRIDGE_MEMPALACE_BIN` | `/opt/chatd/venv/bin/mempalace` | Path to mempalace binary |
| `MEMBRIDGE_TOKENS_FILE` | `/opt/chatd/etc/mempalace.tokens` | Bearer tokens file |

Or create `/opt/chatd/mem-bridge/.env`:

```env
MEMBRIDGE_PALACE_PATH=/opt/chatd/.mempalace/palace
MEMBRIDGE_TOKENS_FILE=/opt/chatd/etc/mempalace.tokens
```

## API

All endpoints (except `/healthz`) require:

```
Authorization: Bearer <token>
```

| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Health check (no auth) |
| GET | `/api/status` | MemPalace status |
| POST | `/api/search` | Semantic search |
| POST | `/api/mine` | Mine new memories from text |
| POST | `/api/recall` | Recall by topic |

### POST /api/search

```json
{ "query": "nginx configuration", "wing": null, "room": null }
```

### POST /api/mine

```json
{ "source": "Today I configured nginx on polyserv.", "wing": null }
```

### POST /api/recall

```json
{ "topic": "polyserv infrastructure", "limit": 10 }
```

## Install

```bash
# As root on the Debian server:
git clone https://github.com/nikita-popov/mem-bridge /opt/chatd/mem-bridge
bash /opt/chatd/mem-bridge/deploy/install.sh
```

Edit `/opt/chatd/etc/mempalace.tokens` – add bearer tokens, one per line:

```
# lines starting with # are comments
pplx_yourtokenhere
```

Then restart:

```bash
systemctl restart mem-bridge
```

## Nginx

Include `deploy/nginx-location.conf` in your `chat.polyserv.xyz` server block:

```bash
include /opt/chatd/mem-bridge/deploy/nginx-location.conf;
nginx -t && systemctl reload nginx
```

## Local dev

```bash
pip install -r requirements.txt
MEMBRIDGE_PALACE_PATH=~/.mempalace/palace uvicorn app.main:app --reload
```

## Adding tokens

Edit the tokens file and restart the service (tokens are loaded at startup):

```bash
echo 'newtoken123' >> /opt/chatd/etc/mempalace.tokens
systemctl restart mem-bridge
```
