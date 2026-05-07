"""MCP server via Streamable HTTP transport.

We build the session manager ourselves so we can wire its lifespan
into the outer Starlette app rather than relying on a nested sub-app.

Starlette does NOT propagate lifespan into Mount()-ed sub-apps, so
mcp.streamable_http_app() used as Mount target will never start the
session_manager task group → RuntimeError on first request.

Correct approach:
  1. Create StreamableHTTPSessionManager from mcp._mcp_server directly.
  2. Start it in the outer app lifespan via `async with session_manager.run()`.
  3. Expose a plain ASGI callable (handler) that calls handle_request.
  4. Wrap with a pure-ASGI auth shim (lifespan-transparent).
"""
from typing import Any
import contextlib

from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.types import ASGIApp, Receive, Scope, Send

from app import mempalace as mp
from app.auth import VALID_TOKENS
from app.config import settings


# ── transport security ────────────────────────────────────────────────────────

extra = settings.extra_allowed_hosts()

if "*" in extra:
    _security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
else:
    _default_hosts   = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    _default_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    _security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_default_hosts + extra,
        allowed_origins=_default_origins
            + [f"https://{h}" for h in extra]
            + [f"http://{h}"  for h in extra],
    )


# ── FastMCP + tools ───────────────────────────────────────────────────────────

mcp = FastMCP(
    name="mem-bridge",
    instructions=(
        "Long-term memory backed by MemPalace. "
        "Use `search` to recall information, `mine` to store new memories, "
        "and `recall` to retrieve memories by topic."
    ),
    transport_security=_security,
)


@mcp.tool()
def search(query: str, wing: str | None = None, room: str | None = None) -> dict[str, Any]:
    """Search memories semantically."""
    return mp.search(query, wing, room).as_dict()


@mcp.tool()
def mine(source: str, wing: str | None = None) -> dict[str, Any]:
    """Store new information into the memory palace."""
    return mp.mine(source, wing).as_dict()


@mcp.tool()
def recall(topic: str, limit: int = 10) -> dict[str, Any]:
    """Recall memories related to a topic."""
    return mp.recall(topic, limit).as_dict()


@mcp.tool()
def status() -> dict[str, Any]:
    """Return the current status of the MemPalace instance."""
    return mp.status().as_dict()


# ── session manager (lifespan managed by outer app) ───────────────────────────

session_manager = StreamableHTTPSessionManager(
    app=mcp._mcp_server,
    event_store=None,
    json_response=False,
    stateless=False,
)


@contextlib.asynccontextmanager
async def mcp_lifespan():
    """Start/stop the session manager task group.

    Call this from the outer Starlette app lifespan:

        async with mcp_lifespan():
            yield
    """
    async with session_manager.run():
        yield


# ── pure-ASGI auth shim ───────────────────────────────────────────────────────

async def _deny(send: Send, status: int, body: bytes) -> None:
    await send({"type": "http.response.start", "status": status,
                "headers": [[b"content-type", b"text/plain"],
                             [b"content-length", str(len(body)).encode()]]})
    await send({"type": "http.response.body", "body": body, "more_body": False})


async def mcp_handler(scope: Scope, receive: Receive, send: Send) -> None:
    """Auth-checked MCP ASGI handler.  Mount this at '/' in the outer router."""
    if scope["type"] == "http" and VALID_TOKENS:
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()
        if not auth.startswith("Bearer "):
            await _deny(send, 401, b"missing bearer token")
            return
        if auth[7:].strip() not in VALID_TOKENS:
            await _deny(send, 403, b"invalid token")
            return

    await session_manager.handle_request(scope, receive, send)
