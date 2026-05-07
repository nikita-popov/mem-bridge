# mem-bridge

Lightweight HTTP bridge that exposes a local [MemPalace](https://github.com/MemPalace/mempalace)
instance as both an MCP server and a REST API.

Runs as an unprivileged system user under systemd, behind an nginx reverse proxy.
Works with any MCP client that supports **Streamable HTTP transport** —
Perplexity, Cursor, Claude Desktop, custom scripts, etc.

## Stack

- **FastAPI** – REST API and app container
- **FastMCP** (`mcp[cli]`) – MCP Streamable HTTP transport
- **Gunicorn + UvicornWorker** – production ASGI server
- **pydantic-settings** – configuration via environment variables / `.env`
- **MemPalace CLI** – invoked as a subprocess; `--palace` path is explicit

## Endpoints

| Path | Description |
|---|---|
| `GET /healthz` | Health check (no auth) |
| `POST /mcp/` | MCP Streamable HTTP – connect MCP clients here |
| `GET /api/status` | REST: MemPalace status |
| `POST /api/search` | REST: semantic search |
| `POST /api/mine` | REST: store memories |
| `POST /api/recall` | REST: recall by topic |

Interactive REST docs: `http://127.0.0.1:8765/docs` (local only by default).

## Connecting Perplexity

1. Open **Account settings → Connectors → + Custom connector**
2. Choose **Remote**
3. MCP Server URL: `https://your-domain/mem-bridge/mcp/`
4. Transport: **Streamable HTTP**
5. Auth: **API Key** → paste a token from your tokens file

## Configuration

All settings are controlled by environment variables prefixed `MEMBRIDGE_`.
Set them in `/etc/mem-bridge/env` (systemd `EnvironmentFile`) or in `.env`.

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

After installation, add bearer tokens and restart:

```bash
echo 'your-secret-token' >> /etc/mem-bridge/tokens
systemctl restart mem-bridge
```

## Nginx

Include `deploy/nginx-location.conf` in your HTTPS server block:

```bash
include /path/to/mem-bridge/deploy/nginx-location.conf;
nginx -t && systemctl reload nginx
```

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit as needed
uvicorn app.main:app --reload
```

## Updating

```bash
cd /opt/mem-bridge
git pull
/opt/mem-bridge/venv/bin/pip install -q -r requirements.txt
systemctl restart mem-bridge
```

## Tokens

Tokens are loaded once at process start.
To add or revoke a token, edit the file and restart:

```bash
echo 'newtoken' >> /etc/mem-bridge/tokens
systemctl restart mem-bridge
```
