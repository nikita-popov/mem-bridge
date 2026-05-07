"""MCP server via Streamable HTTP transport.

Auth is injected as a Starlette middleware so the FastMCP Starlette app
(including its lifespan / session_manager.run()) is used as-is.
Wrapping the ASGI callable directly breaks lifespan events.
"""
from typing import Any
from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
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


# ── auth middleware ────────────────────────────────────────────────────────────

class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests without a valid Bearer token.

    Skipped when VALID_TOKENS is empty (open access / no tokens file).
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if not VALID_TOKENS:
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return Response("missing bearer token", status_code=401)
        if auth[7:].strip() not in VALID_TOKENS:
            return Response("invalid token", status_code=403)
        return await call_next(request)


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


# ── build the final ASGI app ────────────────────────────────────────────────────
# streamable_http_app() returns a Starlette app with lifespan wired up.
# We add BearerAuthMiddleware on top via Starlette middleware injection
# so lifespan events reach the inner app correctly.

def build_mcp_app() -> Any:
    """Return the FastMCP Starlette app with auth middleware added."""
    starlette_app = mcp.streamable_http_app()
    # Inject auth middleware by rebuilding middleware stack
    starlette_app.middleware_stack = BearerAuthMiddleware(
        app=starlette_app.middleware_stack,
    )
    return starlette_app


mcp_app = build_mcp_app()
