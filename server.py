"""Minimal MCP HTTP bridge for MemPalace.

Usage:
    uvicorn server:app

Env vars:
    TOKENS_FILE   path to bearer tokens file (one per line)  [/etc/mem-bridge/tokens]
    PALACE_PATH   path to mempalace palace directory         [mempalace default]
    ALLOWED_HOSTS comma-separated external hostnames         [localhost only]
"""
import os
import contextlib
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.types import Receive, Scope, Send

import mempalace as mp


# ── config ────────────────────────────────────────────────────────────────────

def _load_tokens() -> frozenset[str]:
    path = os.environ.get("TOKENS_FILE", "/etc/mem-bridge/tokens")
    try:
        with open(path) as f:
            return frozenset(
                line.strip() for line in f
                if line.strip() and not line.startswith("#")
            )
    except FileNotFoundError:
        return frozenset()


TOKENS = _load_tokens()

_extra_hosts = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if h.strip()
]

if "*" in _extra_hosts:
    _security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
else:
    _security = TransportSecuritySettings(
        enable_dns_rebinding_protection=bool(_extra_hosts),
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"] + _extra_hosts,
        allowed_origins=(
            ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
            + [f"https://{h}" for h in _extra_hosts]
            + [f"http://{h}"  for h in _extra_hosts]
        ),
    )


# ── FastMCP + tools ───────────────────────────────────────────────────────────

mcp = FastMCP("mem-bridge", transport_security=_security)


@mcp.tool()
def search(query: str, wing: str | None = None, room: str | None = None) -> dict:
    """Search memories semantically."""
    return mp.search(query, wing=wing, room=room)


@mcp.tool()
def mine(source: str, wing: str | None = None) -> dict:
    """Index a file or directory path into the memory palace."""
    return mp.mine(source, wing=wing)


@mcp.tool()
def recall(topic: str, limit: int = 10) -> dict:
    """Recall memories related to a topic."""
    return mp.recall(topic, limit=limit)


@mcp.tool()
def status() -> dict:
    """Return MemPalace status."""
    return mp.status()


# ── session manager ───────────────────────────────────────────────────────────

session_manager = StreamableHTTPSessionManager(
    app=mcp._mcp_server,
    event_store=None,
    json_response=False,
    stateless=True,
)


# ── auth + MCP handler ──────────────────────────────────────────────────────────

async def _deny(send: Send, code: int, msg: bytes) -> None:
    await send({"type": "http.response.start", "status": code,
                "headers": [[b"content-type", b"text/plain"],
                             [b"content-length", str(len(msg)).encode()]]})
    await send({"type": "http.response.body", "body": msg, "more_body": False})


async def mcp_handler(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] == "http" and TOKENS:
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()
        if not auth.startswith("Bearer "):
            await _deny(send, 401, b"missing bearer token")
            return
        if auth[7:].strip() not in TOKENS:
            await _deny(send, 403, b"invalid token")
            return
    await session_manager.handle_request(scope, receive, send)


# ── Starlette app ─────────────────────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def lifespan(_app: Starlette):
    async with session_manager.run():
        yield


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/healthz", lambda r: JSONResponse({"ok": True}), methods=["GET"]),
        Mount("/", app=mcp_handler),
    ],
)
