"""ASGI entry point.

Architecture:
  /           → MCP Streamable HTTP (FastMCP)
  /healthz    → health check (no auth)
  /api/*      → REST endpoints (Bearer auth)

We build a Starlette Router that adds /healthz and /api/* on top of the
MCP app, which handles everything else (POST /, GET /, OPTIONS /, ...).
This avoids app.mount() path-stripping issues.
"""
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from app.routes import build_rest_router
from app.mcp_server import mcp_app


async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


app = Starlette(
    routes=[
        Route("/healthz", healthz, methods=["GET"]),
        Mount("/api", app=build_rest_router()),
        Mount("/", app=mcp_app),
    ],
)
