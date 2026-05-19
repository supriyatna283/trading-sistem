"""API key authentication for mutating / sensitive endpoints."""

from fastapi import Header, HTTPException
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
