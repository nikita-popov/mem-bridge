from fastapi import FastAPI
from app.routes import router

app = FastAPI(
    title="mem-bridge",
    description="HTTP bridge to a local MemPalace instance",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)


@app.get("/healthz", tags=["meta"])
def healthz():
    return {"ok": True}


app.include_router(router, prefix="/api")
