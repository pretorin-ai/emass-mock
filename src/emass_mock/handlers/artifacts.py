"""POST /api/systems/{systemId}/artifacts — stateful handler.

Response shape matches MITRE spec `ArtifactsResponsePutPost` — each data item:
    {"filename": str, "success": bool, "systemId": int, "errors": {...}?}

The real artifacts endpoint accepts multipart uploads of a zipped payload;
this harness accepts JSON descriptors for testing ergonomics. Integrators
testing real upload code paths should mock at the HTTP client layer instead.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..auth import require_api_key
from ..envelope import error, ok
from ..store import get_store

router = APIRouter(prefix="/api", tags=["artifacts"], dependencies=[Depends(require_api_key)])


@router.post("/systems/{system_id}/artifacts")
async def upload_artifacts(system_id: int, payload: list[dict[str, Any]] | dict[str, Any]):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    items = payload if isinstance(payload, list) else [payload]
    data: list[dict[str, Any]] = []
    for art in items:
        stored = {**art, "systemId": system_id}
        record.artifacts.append(stored)
        data.append(
            {
                "filename": art.get("filename"),
                "success": True,
                "systemId": system_id,
            }
        )
    return ok(data)


@router.get("/systems/{system_id}/artifacts")
async def list_artifacts(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return ok(record.artifacts)
