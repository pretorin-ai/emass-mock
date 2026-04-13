"""eMASS API response envelope helpers.

Real eMASS responses follow the shape:
    { "meta": { "code": <http-status> }, "data": [...] | {...} }

Errors mirror this with an "errorCode" / "errorMessage" inside meta.
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"meta": {"code": status_code}, "data": data},
    )


def error(status_code: int, message: str, error_code: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "meta": {
                "code": status_code,
                "errorCode": error_code or f"E{status_code}",
                "errorMessage": message,
            }
        },
    )
