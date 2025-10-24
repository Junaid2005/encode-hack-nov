from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import Settings, get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    api_key: str | None = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """Enforce API key if BACKEND_API_KEY is configured.

    If no BACKEND_API_KEY is set, allow all requests (useful for local dev)
    but consider setting it in production for RBAC/authorization.
    """
    if settings.backend_api_key:
        if not api_key or api_key != settings.backend_api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

