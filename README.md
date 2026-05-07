# mem-bridge

Minimal MCP HTTP bridge for [MemPalace](https://github.com/MemPalace/mempalace).

Single file (`server.py`). No FastAPI. Just `mcp[cli]` + `uvicorn` + `starlette`.

## Endpoints

| Path | Description |
|---|---|
| `GET /healthz` | Health check (no auth) |
| `POST /` | MCP Streamable HTTP |

## Install

```bash
python3 -m venv /opt/mem-bridge/venv
/opt/mem-bridge/venv/bin/pip install -r requirements.txt
mempalace  # must be installed separately
```

## Config (`/etc/mem-bridge/env`)

```
TOKENS_FILE=/etc/mem-bridge/tokens
PALACE_PATH=/opt/chatd/.mempalace/palace
ALLOWED_HOSTS=your-domain.example.com
```

## Run

```bash
systemctl enable --now mem-bridge
```

## Perplexity connector

- URL: `https://your-domain/mem-bridge/`
- Transport: **Streamable HTTP**
- Auth: **API Key** → Bearer token from `/etc/mem-bridge/tokens`
