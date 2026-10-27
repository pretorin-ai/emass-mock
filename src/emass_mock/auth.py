"""Header authentication matching the spec and the observed live API.

The spec's security schemes are ``apiKey`` (header ``api-key``, every call) and
``userId`` (header ``user-uid``, described as needed for PUT, POST, and
DELETE). ``deathlabs/emu``, which runs against the DoD instance, stopped
sending ``user-uid`` on GET in its 4.0.3 release and still works. So:

* ``api-key`` is required on every intercepted request.
* ``user-uid`` is required on writes. ``EMASS_MOCK_REQUIRE_USER_UID_ON_ALL=true``
  extends that to GET for callers who want the stricter posture.

Failures raise ``AuthError``; ``main.py`` renders it in the eMASS error
envelope (``{"meta": {"code": 401, "errorMessage": ...}}``) rather than
FastAPI's ``{"detail": ...}``.

The mock does not terminate TLS, so the DoD PKI client-certificate check is
left to a reverse proxy in front of it.
"""

from __future__ import annotations

from fastapi import Header, Request

from .config import load_settings

WRITE_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})


class AuthError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


async def require_emu_auth(
    request: Request,
    api_key: str | None = Header(default=None, alias="api-key"),
    user_uid: str | None = Header(default=None, alias="user-uid"),
) -> None:
    settings = load_settings()
    if not settings.require_api_key:
        return
    if api_key != settings.api_key:
        raise AuthError(401, "Invalid or missing api-key header")
    needs_uid = request.method.upper() in WRITE_METHODS or settings.require_user_uid_on_all
    if needs_uid and not user_uid:
        raise AuthError(401, "Missing user-uid header; eMASS requires it on PUT, POST, and DELETE")
