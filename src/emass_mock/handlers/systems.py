"""GET /api/systems and /api/systems/{id} (``getSystems``, ``getSystem``).

Returning our seeded system list gives integrators a deterministic anchor
for "which systems exist in this mock?" tests. Without this, a test that
asserts `system.systemId == 1` would break every time Prism re-rolls its
`x-faker` IDs.

The spec's filters (``coamsId``, ``ditprId``, ``includeDecommissioned``,
``policy``, ``registrationType``, ...) are accepted and ignored. Neither
operation is paginated in v3.22.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth import require_emu_auth
from ..envelope import ok
from ..store import SystemRecord, get_store
from ._common import system_or_404

router = APIRouter(prefix="/api", tags=["systems"], dependencies=[Depends(require_emu_auth)])


def _row(record: SystemRecord) -> dict:
    return {"systemId": record.system_id, "name": record.name, "acronym": record.acronym}


@router.get("/systems")
async def list_systems():
    return ok([_row(s) for s in get_store().list_systems()])


@router.get("/systems/{system_id}")
async def get_system(system_id: int):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record
    return ok(_row(record))
