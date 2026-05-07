"""MCP server via Streamable HTTP transport.

Exposes MemPalace tools to any MCP client (Perplexity, Cursor, Claude, etc.).

Two things that must be set correctly for external clients (e.g. Perplexity):

1. streamable_http_path='/' so the endpoint is POST /, not POST /mcp
2. transport_security must allow the external hostname of the reverse proxy;
   by default FastMCP only allows localhost (DNS rebinding protection).
   Set MEMBRIDGE_ALLOWED_HOSTS=your-domain.example.com in the env file.
"""
from typing import Any
from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import Response
from app import mempalace as mp
from app.auth import VALID_TOKENS
from app.config import settings

# ── transport security ──────────────────────────────────────────────────────────

extra = settings.extra_allowed_hosts()

if "*" in extra:
    # Disable DNS rebinding protection entirely
    _security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
else:
    # Keep localhost + add any explicitly configured external hosts
    _default_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    _default_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    _security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_default_hosts + extra,
        allowed_origins=_default_origins + [
            f"https://{h}" for h in extra
        ] + [
            f"http://{h}" for h in extra
        ],
    )

# ── FastMCP instance ──────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="mem-bridge",
    instructions=(
        "Long-term memory backed by MemPalace. "
        "Use `search` to recall information, `mine` to store new memories, "
        "and `recall` to retrieve memories by topic."
    ),
    # Endpoint lives at POST / (not POST /mcp which is the default)
    streamable_http_path="/",
    transport_security=_security,
)


# ── auth middleware ──────────────────────────────────────────────────────────

async def _check_auth(request: Request) -> Response | None:
    """Return 401/403 Response if auth fails, else None."""
    if not VALID_TOKENS:
        return None  # no tokens configured – open access
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return Response("missing bearer token", status_code=401)
    if auth[7:].strip() not in VALID_TOKENS:
        return Response("invalid token", status_code=403)
    return None


# ── MCP tools ─────────────────────────────────────────────────────────────────

@mcp.tool()
def search(
    query: str,
    wing: str | None = None,
    room: str | None = None,
) -> dict[str, Any]:
    """Search memories semantically.

    Args:
        query: Natural language search query.
        wing:  Optional wing name to narrow the search scope.
        room:  Optional room name to narrow the search scope.
    """
    return mp.search(query, wing, room).as_dict()


@mcp.tool()
def mine(
    source: str,
    wing: str | None = None,
) -> dict[str, Any]:
    """Store new information into the memory palace.

    Args:
        source: The text to mine and store as memories.
        wing:   Optional wing to place the memories in.
    """
    return mp.mine(source, wing).as_dict()


@mcp.tool()
def recall(
    topic: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Recall memories related to a topic.

    Args:
        topic: Topic or keyword to recall memories about.
        limit: Maximum number of memories to return (default 10).
    """
    return mp.recall(topic, limit).as_dict()


@mcp.tool()
def status() -> dict[str, Any]:
    """Return the current status of the MemPalace instance."""
    return mp.status().as_dict()


# ── ASGI app with auth wrapper ────────────────────────────────────────────────

_mcp_asgi = mcp.streamable_http_app()


async def mcp_app(scope: dict, receive: Any, send: Any) -> None:
    """ASGI wrapper: checks Bearer auth, then delegates to FastMCP."""
    if scope["type"] == "http":
        request = Request(scope, receive)
        deny = await _check_auth(request)
        if deny is not None:
            await deny(scope, receive, send)
            return
    await _mcp_asgi(scope, receive, send)
