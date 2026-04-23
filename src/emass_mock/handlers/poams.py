"""POST /api/systems/{systemId}/poams — stateful handler.

Response shape matches MITRE spec `PoamResponsePostPutDelete`:
    {"meta": {"code": 200}, "data": [PoamPostPutDel, ...]}
Each `PoamPostPutDel` row has `systemId`, `poamId` (server-assigned),
and `externalUid` if provided.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..auth import require_emu_auth
from ..envelope import error, ok
from ..store import get_store

router = APIRouter(prefix="/api", tags=["poams"], dependencies=[Depends(require_emu_auth)])


@router.post("/systems/{system_id}/poams")
async def create_poams(system_id: int, payload: list[dict[str, Any]]):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    data: list[dict[str, Any]] = []
    for poam in payload:
        poam_id = record.next_poam_id()
        stored = {**poam, "systemId": system_id, "poamId": poam_id}
        record.poams.append(stored)
        item = {"systemId": system_id, "poamId": poam_id}
        if poam.get("externalUid") is not None:
            item["externalUid"] = poam["externalUid"]
        data.append(item)
    return ok(data)


@router.get("/systems/{system_id}/poams")
async def list_poams(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return ok(record.poams)
