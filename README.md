# mem-bridge

Lightweight HTTP bridge that exposes a local [MemPalace](https://github.com/MemPalace/mempalace)
instance as a REST API.

Runs as an unprivileged system user under systemd, behind an nginx reverse proxy.
Works with any HTTP client that supports Bearer token authentication — Perplexity,
Cursor, custom scripts, etc.

## Stack

- **FastAPI** – request handling
- **Gunicorn + gevent** – production server
- **pydantic-settings** – configuration via environment variables / `.env`
- **MemPalace CLI** – invoked as a subprocess; `--palace` path is explicit

## Configuration

All settings are controlled by environment variables prefixed `MEMBRIDGE_`.
You can set them in the systemd `EnvironmentFile` (`/etc/mem-bridge/env` by default)
or in a `.env` file in the working directory.

See [`.env.example`](.env.example) for all available variables:

| Variable | Default | Description |
|---|---|---|
| `MEMBRIDGE_PALACE_PATH` | _(empty – MemPalace default)_ | Path passed to `mempalace --palace` |
| `MEMBRIDGE_MEMPALACE_BIN` | `mempalace` | Path to the mempalace binary |
| `MEMBRIDGE_TOKENS_FILE` | `/etc/mem-bridge/tokens` | Bearer tokens file (one per line) |
| `MEMBRIDGE_BIND` | `127.0.0.1:8765` | Gunicorn bind address |
| `MEMBRIDGE_WORKERS` | `1` | Number of gunicorn workers |

## Install

```bash
git clone https://github.com/nikita-popov/mem-bridge
bash mem-bridge/deploy/install.sh
```

All paths and the service user are configurable:

```bash
bash mem-bridge/deploy/install.sh \
  --user  myuser \
  --dir   /srv/mem-bridge \
  --conf  /etc/mem-bridge \
  --palace /data/mempalace/palace
```

The installer will:
1. Create the system user (if absent)
2. Create directories and config files
3. Bootstrap a Python virtualenv and install dependencies + `mempalace`
4. Register and start the `mem-bridge.service` systemd unit

After installation, add bearer tokens to the tokens file and restart:

```bash
echo 'your-secret-token' >> /etc/mem-bridge/tokens
systemctl restart mem-bridge
```

## Nginx

Include `deploy/nginx-location.conf` in your HTTPS server block,
adjusting the subpath (`/mem-bridge/`) as needed:

```nginx
include /path/to/mem-bridge/deploy/nginx-location.conf;
```

Then test and reload:

```bash
nginx -t && systemctl reload nginx
```

## API

All endpoints except `/healthz` require `Authorization: Bearer <token>`.

| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Health check (no auth) |
| GET | `/api/status` | MemPalace palace status |
| POST | `/api/search` | Semantic search |
| POST | `/api/mine` | Mine new memories from text |
| POST | `/api/recall` | Recall by topic |

Interactive docs: `http://127.0.0.1:8765/docs` (local only by default).

### POST /api/search

```json
{ "query": "nginx configuration", "wing": null, "room": null }
```

### POST /api/mine

```json
{ "source": "Deployed mem-bridge on Debian today.", "wing": null }
```

### POST /api/recall

```json
{ "topic": "infrastructure", "limit": 10 }
```

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit as needed
uvicorn app.main:app --reload
```

## Tokens

Tokens are loaded once at process start. To add or revoke a token,
edit the tokens file and restart the service:

```bash
echo 'newtoken' >> /etc/mem-bridge/tokens
systemctl restart mem-bridge
```
