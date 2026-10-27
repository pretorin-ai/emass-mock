"""Response envelope helpers matching the MITRE eMASS OpenAPI spec.

Per the spec (eMASSRestOpenApi.yaml):
- Success (Response200): {"meta": {"code": 200}, "data": <...>}
- Paginated GETs add a sibling: {"meta": ..., "data": [...], "pagination": {...}}
- 400 BadRequest:   {"meta": {"code": 400, "errorMessage": "..."}}
- 401 Unauthorized: {"meta": {"code": 401, "errorMessage": "..."}}
- 403 Forbidden:    {"meta": {"code": 403, "errorMessage": "..."}}
- 404 NotFound:     {"meta": {"code": 404, "errorMessage": "..."}}
- 405 MethodNotAllowed
- 411 LengthRequired
- 500 InternalServerError: {"meta": {"code": 500, "errorMessage": "..."}}

Success envelope `meta` is ONLY {code: 200}. Error envelopes never carry data.
Do not conflate the two shapes.

Per-row failures inside a 200 use the spec's ``Errors`` type: an array of one
to twenty-five strings shaped like ``"key: value"``.
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any) -> JSONResponse:
    """Spec-conformant 200 response envelope."""
    return JSONResponse(status_code=200, content={"meta": {"code": 200}, "data": data})


def paginated(
    data: list[Any], *, page_index: int, page_size: int, total: int, url: str
) -> JSONResponse:
    """200 envelope with the spec's ``Pagination`` block (hw/sw baseline GETs)."""
    total_pages = max(1, -(-total // page_size)) if page_size else 1
    base = url.split("?", 1)[0]

    def link(index: int) -> str:
        return f"{base}?pageIndex={index}&pageSize={page_size}"

    pagination = {
        "pageIndex": page_index,
        "pageSize": page_size,
        "totalCount": total,
        "totalPages": total_pages,
        "prevPageUrl": link(page_index - 1) if page_index > 0 else "",
        "nextPageUrl": link(page_index + 1) if page_index + 1 < total_pages else "",
    }
    return JSONResponse(
        status_code=200,
        content={"meta": {"code": 200}, "data": data, "pagination": pagination},
    )


def error(status_code: int, message: str) -> JSONResponse:
    """Spec-conformant error envelope. Meta has no `data` field on errors."""
    return JSONResponse(
        status_code=status_code,
        content={"meta": {"code": status_code, "errorMessage": message}},
    )


def row_errors(*messages: str) -> list[str]:
    """``Errors`` for a ``success: false`` row: 1 to 25 ``"key: value"`` strings."""
    return list(messages)[:25] or ["error: unspecified"]
