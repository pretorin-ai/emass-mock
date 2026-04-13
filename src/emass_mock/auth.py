"""Auth dependency: validates the `api-key` header.

Real eMASS also requires a DoD-issued mTLS client certificate at the network
edge. The mock supports mTLS at the uvicorn/proxy layer (out of band) but does
NOT enforce certificate validation at the application layer — that's a TLS
termination concern. See README for mTLS setup with a reverse proxy.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from .config import load_settings


async def require_api_key(api_key: str | None = Header(default=None, alias="api-key")) -> None:
    settings = load_settings()
    if not settings.require_api_key:
        return
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing api-key header",
        )
