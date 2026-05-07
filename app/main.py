from fastapi import FastAPI
from starlette.routing import Mount
from app.routes import router
from app.mcp_server import mcp_app

app = FastAPI(
    title="mem-bridge",
    description="HTTP bridge to a local MemPalace instance",
    version="0.3.0",
    docs_url="/docs",
    redoc_url=None,
)


@app.get("/healthz", tags=["meta"])
def healthz():
    return {"ok": True}


# REST API (optional, for direct use / debugging)
app.include_router(router, prefix="/api")

# MCP Streamable HTTP – Perplexity and other MCP clients connect here.
# Endpoint: POST /mcp/  (or whatever subpath nginx strips to)
app.mount("/mcp", mcp_app)
