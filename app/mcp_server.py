"""MCP server via Streamable HTTP transport.

We wrap the FastMCP Starlette app with a minimal pure-ASGI shim that:
  - forwards lifespan events unchanged (so session_manager.run() works)
  - checks Bearer auth on HTTP requests before delegating

Do NOT use BaseHTTPMiddleware or patch middleware_stack — both break
lifespan propagation in Starlette.
"""
from typing import Any
from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import Response
from app import mempalace as mp
from app.auth import VALID_TOKENS
from app.config import settings


# ── transport security ──────────────────────────────────────────────────────────

extra = settings.extra_allowed_hosts()

if "*" in extra:
    _security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
else:
    _default_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    _default_origins = [
        "http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*",
    ]
    _security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_default_hosts + extra,
        allowed_origins=_default_origins
            + [f"https://{h}" for h in extra]
            + [f"http://{h}" for h in extra],
    )


# ── FastMCP instance ─────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="mem-bridge",
    instructions=(
        "Long-term memory backed by MemPalace. "
        "Use `search` to recall information, `mine` to store new memories, "
        "and `recall` to retrieve memories by topic."
    ),
    streamable_http_path="/",
    transport_security=_security,
)


# ── tools ──────────────────────────────────────────────────────────────────────

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


# ── pure-ASGI auth shim ──────────────────────────────────────────────────────────

class _AuthShim:
    """Thin ASGI wrapper around an inner app.

    - lifespan events  → forwarded directly, no auth check
    - http events      → Bearer token checked first; 401/403 if invalid
    """

    def __init__(self, inner: ASGIApp) -> None:
        self._inner = inner

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not VALID_TOKENS:
            # Pass lifespan + websocket scopes straight through.
            # Also skip auth when no tokens are configured.
            await self._inner(scope, receive, send)
            return

        # Check Bearer token before touching the inner app.
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()
        if not auth.startswith("Bearer "):
            await _deny(scope, send, 401, b"missing bearer token")
            return
        if auth[7:].strip() not in VALID_TOKENS:
            await _deny(scope, send, 403, b"invalid token")
            return

        await self._inner(scope, receive, send)


async def _deny(scope: Scope, send: Send, status: int, body: bytes) -> None:
    await send({"type": "http.response.start", "status": status,
                "headers": [[b"content-type", b"text/plain"],
                             [b"content-length", str(len(body)).encode()]]})
    await send({"type": "http.response.body", "body": body, "more_body": False})


# Exported app: FastMCP Starlette app wrapped with auth shim.
# The Starlette app retains its own lifespan; the shim is transparent to it.
mcp_app: ASGIApp = _AuthShim(mcp.streamable_http_app())
