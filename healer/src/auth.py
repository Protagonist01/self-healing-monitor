import secrets
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

from healer.src.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_header = HTTPBearer(auto_error=False)


def verify_api_key(
    api_key: str = Security(api_key_header),
    bearer: HTTPAuthorizationCredentials = Security(bearer_header),
):
    """
    FastAPI dependency that enforces API-key authentication on protected endpoints.
    If HEALER_API_KEY is not configured, the check is skipped (local dev mode).
    """
    if not settings.HEALER_API_KEY:
        return None

    if not isinstance(api_key, str) and isinstance(bearer, HTTPAuthorizationCredentials):
        api_key = bearer.credentials
    if isinstance(api_key, str) and secrets.compare_digest(api_key, settings.HEALER_API_KEY):
        return api_key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key. Provide it via the X-API-Key header.",
    )
