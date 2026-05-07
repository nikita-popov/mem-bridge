from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from pydantic import BaseModel, ValidationError
from app.auth import check_bearer
from app import mempalace as mp
import json


async def _parse(request: Request, model):
    try:
        body = await request.json()
        return model(**body), None
    except (ValidationError, json.JSONDecodeError) as exc:
        return None, JSONResponse({"error": str(exc)}, status_code=422)


# ── request models (plain dataclasses, no FastAPI) ───────────────────────────

class SearchReq(BaseModel):
    query: str
    wing: str | None = None
    room: str | None = None


class MineReq(BaseModel):
    source: str
    wing: str | None = None


class RecallReq(BaseModel):
    topic: str
    limit: int = 10


# ── handlers ────────────────────────────────────────────────────────────────────

async def get_status(request: Request) -> JSONResponse:
    deny = check_bearer(request)
    if deny:
        return deny
    return JSONResponse(mp.status().as_dict())


async def post_search(request: Request) -> JSONResponse:
    deny = check_bearer(request)
    if deny:
        return deny
    req, err = await _parse(request, SearchReq)
    if err:
        return err
    return JSONResponse(mp.search(req.query, req.wing, req.room).as_dict())


async def post_mine(request: Request) -> JSONResponse:
    deny = check_bearer(request)
    if deny:
        return deny
    req, err = await _parse(request, MineReq)
    if err:
        return err
    return JSONResponse(mp.mine(req.source, req.wing).as_dict())


async def post_recall(request: Request) -> JSONResponse:
    deny = check_bearer(request)
    if deny:
        return deny
    req, err = await _parse(request, RecallReq)
    if err:
        return err
    return JSONResponse(mp.recall(req.topic, req.limit).as_dict())


def build_rest_router() -> Starlette:
    return Starlette(routes=[
        Route("/status",  get_status,  methods=["GET"]),
        Route("/search",  post_search, methods=["POST"]),
        Route("/mine",    post_mine,   methods=["POST"]),
        Route("/recall",  post_recall, methods=["POST"]),
    ])
