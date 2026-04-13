"""PUT /api/systems/{system_id}/controls — update control implementations.

Mirrors the eMASS behavior where an array of control records is submitted in
one call. Per-control failures can be injected via the admin API.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..auth import require_api_key
from ..envelope import error, ok
from ..failures import get_failures
from ..store import get_store

router = APIRouter(prefix="/api", tags=["controls"], dependencies=[Depends(require_api_key)])


@router.put("/systems/{system_id}/controls")
async def update_controls(system_id: int, payload: list[dict[str, Any]]):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    failures = get_failures()
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for ctrl in payload:
        acronym = str(ctrl.get("acronym") or ctrl.get("controlAcronym") or "").upper()
        injected = failures.control_status.get(acronym)
        if injected is not None and injected >= 400:
            rejected.append(
                {
                    "acronym": acronym,
                    "errorCode": "INJECTED",
                    "errorMessage": f"Injected failure ({injected}) for {acronym}",
                }
            )
            continue

        record.controls[acronym] = ctrl
        accepted.append({"acronym": acronym, "status": "accepted"})

    # eMASS returns 200 with a mixed result set even on partial failure.
    return ok({"accepted": accepted, "rejected": rejected})


@router.get("/systems/{system_id}/controls")
async def list_controls(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return ok(list(record.controls.values()))
