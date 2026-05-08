# mem-bridge

Minimal MCP Streamable HTTP bridge for [MemPalace](https://github.com/MemPalace/mempalace).

Single file (`server.py`). No FastAPI. Just `mcp[cli]` + `uvicorn` + `starlette`.

## Endpoints

| Path | Description |
|---|---|
| `GET /healthz` | Health check (no auth) |
| `POST /` | MCP Streamable HTTP (Bearer token required) |

## Install

```bash
python3 -m venv /opt/mem-bridge/venv
/opt/mem-bridge/venv/bin/pip install -r requirements.txt
# mempalace must be installed in the same venv:
/opt/mem-bridge/venv/bin/pip install mempalace
```

## Config

Create `/etc/mem-bridge/env` (or `.env` in the project root):

```env
MEMBRIDGE_TOKENS_FILE=/etc/mem-bridge/tokens
MEMBRIDGE_PALACE_PATH=/opt/chatd/.mempalace/palace
MEMBRIDGE_ALLOWED_HOSTS=your-domain.example.com
```

Create `/etc/mem-bridge/tokens` — one Bearer token per line:

```
# generated with: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
your-secret-token-here
```

## Run

```bash
# directly
uvicorn server:app --host 127.0.0.1 --port 8765

# via systemd
systemctl enable --now mem-bridge
```

## Perplexity connector

- **URL**: `https://your-domain/mem-bridge/`
- **Transport**: Streamable HTTP
- **Auth**: API Key → Bearer token from `/etc/mem-bridge/tokens`
