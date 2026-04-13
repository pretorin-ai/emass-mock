"""GET /api/systems and /api/systems/{id} — stateful handlers.

Returning our seeded system list gives integrators a deterministic anchor
for "which systems exist in this mock?" tests. Without this, a test that
asserts `system.systemId == 1` would break every time Prism re-rolls its
`x-faker` IDs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import require_api_key
from ..envelope import error, ok
from ..store import get_store

router = APIRouter(prefix="/api", tags=["systems"], dependencies=[Depends(require_api_key)])


@router.get("/systems")
async def list_systems(
    pageSize: int = Query(default=25, ge=1, le=1000),
    pageIndex: int = Query(default=0, ge=0),
):
    systems = get_store().list_systems()
    start = pageIndex * pageSize
    page = [
        {"systemId": s.system_id, "name": s.name, "acronym": s.acronym}
        for s in systems[start : start + pageSize]
    ]
    return ok(page)


@router.get("/systems/{system_id}")
async def get_system(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return ok({"systemId": record.system_id, "name": record.name, "acronym": record.acronym})
