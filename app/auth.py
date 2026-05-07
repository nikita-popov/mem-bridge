from starlette.requests import Request
from starlette.responses import JSONResponse
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


# Loaded once at process start; restart the service to pick up new tokens.
VALID_TOKENS: frozenset[str] = _load_tokens()


def check_bearer(request: Request) -> JSONResponse | None:
    """Return a JSONResponse error if auth fails, else None."""
    if not VALID_TOKENS:
        return None  # no tokens configured – open access
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"error": "missing bearer token"}, status_code=401)
    if auth[7:].strip() not in VALID_TOKENS:
        return JSONResponse({"error": "invalid token"}, status_code=403)
    return None
