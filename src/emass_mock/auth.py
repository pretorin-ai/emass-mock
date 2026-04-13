"""Auth: validates the `api-key` header per the MITRE eMASS OpenAPI spec.

The spec also defines a `user-uid` header for write operations, but MITRE's
public mock server accepts any value. We mirror that permissiveness: user-uid
is read if present but not validated. Extend if you need strict checks.

Real eMASS additionally requires a DoD-issued mTLS client certificate at the
network boundary. mTLS is out of scope for this test harness — terminate TLS
with a reverse proxy if your integration needs to exercise that code path.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from .config import load_settings
from .envelope import error


async def require_api_key(api_key: str | None = Header(default=None, alias="api-key")) -> None:
    settings = load_settings()
    if not settings.require_api_key:
        return
    if api_key != settings.api_key:
        # eMASS returns 401 with the spec-conformant error envelope.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing api-key header",
        )


def unauthorized_response() -> object:
    """Reusable 401 in spec shape (for middleware use)."""
    return error(401, "Invalid or missing api-key header")
