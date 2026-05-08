# mem-bridge

Minimal MCP Streamable HTTP bridge that proxies **any** local MCP stdio server
over HTTP with Bearer-token auth.

Designed for [MemPalace](https://github.com/MemPalace/mempalace) but works with
any `mcp` stdio server. Single file (`server.py`), no FastAPI.

## How it works

```
MCP client (HTTPS)
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

No hardcoded tool list. Adding tools to the upstream server = they appear automatically.

## Endpoints

| Path | Auth | Description |
|---|---|---|
| `GET /healthz` | — | Health check |
| `POST /` | Bearer | MCP Streamable HTTP |

## Install

```bash
python3 -m venv /opt/mem-bridge/venv
/opt/mem-bridge/venv/bin/pip install -r requirements.txt
```

`mempalace` (or your upstream server) must be installed and accessible via
`MEMBRIDGE_MEMPALACE_CMD`.

## Config (`/etc/mem-bridge/env` or `.env`)

```env
MEMBRIDGE_MEMPALACE_CMD=/path/to/venv/bin/python -m mempalace.mcp_server
MEMBRIDGE_TOKENS_FILE=/etc/mem-bridge/tokens
MEMBRIDGE_ALLOWED_HOSTS=your-domain.example.com
# Pass palace path to the subprocess:
MEMPALACE_PALACE_PATH=/path/to/.mempalace/palace
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

## MCP connector

- **URL**: `https://your-domain/`
- **Transport**: Streamable HTTP
- **Auth**: Bearer token from `/etc/mem-bridge/tokens`
