"""POST /api/systems/{system_id}/poams — create POA&Ms."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..auth import require_api_key
from ..envelope import error, ok
from ..store import get_store

router = APIRouter(prefix="/api", tags=["poams"], dependencies=[Depends(require_api_key)])


@router.post("/systems/{system_id}/poams")
async def create_poams(system_id: int, payload: list[dict[str, Any]]):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    record.poams.extend(payload)
    # Assign synthetic poamIds so clients can correlate.
    data = [
        {"poamId": 1000 + len(record.poams) - len(payload) + i, "status": "accepted"}
        for i, _ in enumerate(payload)
    ]
    return ok(data)


@router.get("/systems/{system_id}/poams")
async def list_poams(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return ok(record.poams)
