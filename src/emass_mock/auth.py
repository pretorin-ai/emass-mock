"""Auth helpers aligned to the working EMU client pattern."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from .config import load_settings
from .envelope import error


async def require_emu_auth(
    api_key: str | None = Header(default=None, alias="api-key"),
    user_uid: str | None = Header(default=None, alias="user-uid"),
) -> None:
    settings = load_settings()
    if not settings.require_api_key:
        return
    if api_key != settings.api_key:
        # eMASS returns 401 with the spec-conformant error envelope.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing api-key header",
        )
    if settings.require_user_uid_on_all and not user_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing user-uid header",
        )


def unauthorized_response() -> object:
    """Reusable 401 in spec shape (for middleware use)."""
    return error(401, "Invalid or missing api-key header")
