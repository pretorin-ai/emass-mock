"""Request middleware: applies failure-injection rules before routing."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .envelope import error
from .failures import get_failures, maybe_sleep


class FailureInjectionMiddleware(BaseHTTPMiddleware):
    """Short-circuits matching requests with a configured error status."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # Admin + UI routes bypass failure injection so operators can always recover.
        path = request.url.path
        if path.startswith("/_admin") or path.startswith("/ui") or path == "/health":
            return await call_next(request)

        await maybe_sleep()
        failures = get_failures()

        if failures.global_status is not None:
            return _inject(failures.global_status)

        path_status = failures.path_status.get(request.url.path)
        if path_status is not None:
            return _inject(path_status)

        return await call_next(request)


def _inject(status_code: int) -> JSONResponse:
    return error(status_code, f"Injected failure ({status_code})")
