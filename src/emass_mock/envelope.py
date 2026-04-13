"""Response envelope helpers matching the MITRE eMASS OpenAPI spec.

Per the spec (eMASSRestOpenApi.yaml):
- Success (Response200): {"meta": {"code": 200}, "data": <...>}
- 400 BadRequest:   {"meta": {"code": 400, "errorMessage": "..."}}
- 401 Unauthorized: {"meta": {"code": 401, "errorMessage": "..."}}
- 403 Forbidden:    {"meta": {"code": 403, "errorMessage": "..."}}
- 404 NotFound:     {"meta": {"code": 404, "errorMessage": "..."}}
- 405 MethodNotAllowed
- 411 LengthRequired
- 500 InternalServerError: {"meta": {"code": 500, "errorMessage": "..."}}

Success envelope `meta` is ONLY {code: 200}. Error envelopes never carry data.
Do not conflate the two shapes.
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any) -> JSONResponse:
    """Spec-conformant 200 response envelope."""
    return JSONResponse(status_code=200, content={"meta": {"code": 200}, "data": data})


def error(status_code: int, message: str) -> JSONResponse:
    """Spec-conformant error envelope. Meta has no `data` field on errors."""
    return JSONResponse(
        status_code=status_code,
        content={"meta": {"code": status_code, "errorMessage": message}},
    )
