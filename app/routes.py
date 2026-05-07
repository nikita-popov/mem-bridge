from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth import require_bearer
from app import mempalace as mp

router = APIRouter(dependencies=[Depends(require_bearer)])


# ── request models ──────────────────────────────────────────────────────────

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


# ── endpoints ────────────────────────────────────────────────────────────────

@router.get("/status")
def get_status():
    return mp.status().as_dict()


@router.post("/search")
def post_search(req: SearchReq):
    return mp.search(req.query, req.wing, req.room).as_dict()


@router.post("/mine")
def post_mine(req: MineReq):
    return mp.mine(req.source, req.wing).as_dict()


@router.post("/recall")
def post_recall(req: RecallReq):
    return mp.recall(req.topic, req.limit).as_dict()
