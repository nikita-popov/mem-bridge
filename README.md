# mem-bridge

Minimal MCP Streamable HTTP bridge that proxies **any** local MCP stdio server
over HTTP with Bearer-token auth.

Designed for [MemPalace](https://github.com/MemPalace/mempalace) but works with
any `mcp` stdio server. Single file (`server.py`), no FastAPI.

## How it works

```
Perplexity (HTTPS)
      │  Bearer token
      ▼
  mem-bridge (uvicorn)
      │  MCP stdio subprocess
      ▼
  mempalace.mcp_server
```

On startup mem-bridge:
1. Spawns the upstream MCP stdio server as a subprocess (`MCPClient`)
2. Calls `list_tools()` on it to discover all available tools
3. Registers every discovered tool as a passthrough FastMCP tool
4. Serves them over Streamable HTTP with Bearer-token auth

No hardcoded tool list. Adding tools to MemPalace = they appear automatically.

## Endpoints

| Path | Auth | Description |
|---|---|---|
| `GET /healthz` | — | Health check |
| `POST /` | Bearer | MCP Streamable HTTP |

## Install

```bash
python3 -m venv /opt/mem-bridge/venv
/opt/mem-bridge/venv/bin/pip install -r requirements.txt
# mempalace must be installed in the same venv:
/opt/mem-bridge/venv/bin/pip install mempalace
```

## Config (`/etc/mem-bridge/env` or `.env`)

```env
MEMBRIDGE_MEMPALACE_CMD=/opt/mem-bridge/venv/bin/python -m mempalace.mcp_server
MEMBRIDGE_TOKENS_FILE=/etc/mem-bridge/tokens
MEMBRIDGE_ALLOWED_HOSTS=chat.example.com
# Pass palace path to the subprocess:
MEMPALACE_PALACE_PATH=/opt/chatd/.mempalace/palace
```

Create `/etc/mem-bridge/tokens` — one Bearer token per line:
```
# generate: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
your-secret-token-here
```

## Run

```bash
# directly
uvicorn server:app --host 127.0.0.1 --port 8765

# via systemd (EnvironmentFile=/etc/mem-bridge/env)
systemctl enable --now mem-bridge
```

## Perplexity connector

- **URL**: `https://your-domain/mem-bridge/`
- **Transport**: Streamable HTTP
- **Auth**: API Key → Bearer token from `/etc/mem-bridge/tokens`
