"""ASGI entry point.

Routing:
  GET  /healthz  → health check (no auth)
  *    /api/*    → REST endpoints (Bearer auth checked inside routes.py)
  *    /*        → MCP Streamable HTTP (auth inside mcp_handler)

Lifespan starts the FastMCP session_manager task group.
"""
import contextlib

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount

from app.mcp_server import mcp_lifespan, mcp_handler
from app.routes import build_rest_router


async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with mcp_lifespan():
        yield


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/healthz", healthz, methods=["GET"]),
        Mount("/api", app=build_rest_router()),
        Mount("/", app=mcp_handler),
    ],
)
