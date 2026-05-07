from fastapi import Header, HTTPException
from app.config import settings


def _load_tokens() -> frozenset[str]:
    p = settings.tokens_file
    if not p.exists():
        return frozenset()
    return frozenset(
        line.strip()
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


# Loaded once at import time; restart service to pick up new tokens.
VALID_TOKENS: frozenset[str] = _load_tokens()


def require_bearer(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization[7:].strip()
    if token not in VALID_TOKENS:
        raise HTTPException(status_code=403, detail="invalid token")
