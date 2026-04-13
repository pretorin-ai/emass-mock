"""POST /api/systems/{system_id}/artifacts — upload artifacts (JSON form).

The real eMASS artifact endpoint supports multipart uploads with a zipped
payload; the mock accepts JSON artifact descriptors for easier testing.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..auth import require_api_key
from ..envelope import error, ok
from ..store import get_store

router = APIRouter(prefix="/api", tags=["artifacts"], dependencies=[Depends(require_api_key)])


@router.post("/systems/{system_id}/artifacts")
async def upload_artifact(system_id: int, payload: dict[str, Any] | list[dict[str, Any]]):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    items = payload if isinstance(payload, list) else [payload]
    record.artifacts.extend(items)
    return ok([{"status": "accepted", "filename": a.get("filename", "artifact")} for a in items])


@router.get("/systems/{system_id}/artifacts")
async def list_artifacts(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return ok(record.artifacts)
