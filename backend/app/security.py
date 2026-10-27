"""API key authentication for mutating / sensitive endpoints."""

import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request
from app.config import get_settings


def require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> None:
    """
    Protect write endpoints with X-API-Key header.
    - Production: API_KEY must be set; requests without valid key are rejected.
    - Development: if API_KEY is empty, allow (local convenience with warning at startup).
    """
    settings = get_settings()

    if not settings.API_KEY:
        if settings.APP_ENV == "production":
            raise HTTPException(
                status_code=503,
                detail="API_KEY is not configured on the server",
            )
        return

    if not x_api_key or x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ── Simple in-memory sliding-window rate limiter ─────────────────────────────
# Protects expensive endpoints (LLM calls) that are consumed via EventSource and
# therefore cannot carry an X-API-Key header. Per-process, per-client-IP; good
# enough to stop accidental/abusive loops. Use Redis if you run multiple workers.
_RATE_BUCKETS: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(name: str, max_calls: int, window_sec: int = 60):
    """FastAPI dependency factory: allow `max_calls` per `window_sec` per client IP."""

    def _dependency(request: Request) -> None:
        now = time.monotonic()
        key = f"{name}:{_client_ip(request)}"
        bucket = _RATE_BUCKETS[key]
        while bucket and now - bucket[0] > window_sec:
            bucket.popleft()
        if len(bucket) >= max_calls:
            retry_after = max(1, int(window_sec - (now - bucket[0])))
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)
        # Opportunistic cleanup so idle clients don't accumulate forever
        if len(_RATE_BUCKETS) > 5000:
            for k in [k for k, v in _RATE_BUCKETS.items() if not v or now - v[-1] > window_sec]:
                _RATE_BUCKETS.pop(k, None)

    return _dependency
