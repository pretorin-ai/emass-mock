"""PUT /api/systems/{systemId}/controls — stateful handler.

Response shape matches MITRE spec `ControlsResponsePut`:
    {"meta": {"code": 200}, "data": [ControlsPut, ...]}
where each `ControlsPut` is:
    {"acronym": str, "success": bool, "systemId": int, ...}

Real eMASS returns a `ControlsPut` row per submitted control. `success=false`
rows carry an `errors` sub-object. Per-item failures can be injected through
the failure-injection admin API (acronym → status code).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth import require_emu_auth
from ..envelope import error, ok
from ..failures import get_failures
from ..store import get_store

router = APIRouter(prefix="/api", tags=["controls"], dependencies=[Depends(require_emu_auth)])

_REQUIRED_FIELDS = (
    "acronym",
    "responsibleEntities",
    "controlDesignation",
    "estimatedCompletionDate",
    "implementationNarrative",
)
_SLCM_REQUIRED = (
    "slcmCriticality",
    "slcmFrequency",
    "slcmMethod",
    "slcmReporting",
    "slcmTracking",
    "slcmComments",
)


def _validate_control(ctrl: dict[str, Any]) -> str | None:
    missing = [field for field in _REQUIRED_FIELDS if not ctrl.get(field)]
    if missing:
        acronym = ctrl.get("acronym") or "<unknown>"
        return f"Control {acronym} missing required fields: {', '.join(missing)}"

    status = ctrl.get("implementationStatus")
    if status in {"Planned", "Implemented"}:
        slcm_missing = [field for field in _SLCM_REQUIRED if not ctrl.get(field)]
        if slcm_missing:
            return (
                f"Control {ctrl.get('acronym')} missing SLCM fields for {status}: "
                f"{', '.join(slcm_missing)}"
            )
    if status == "Not Applicable" and not ctrl.get("naJustification"):
        return f"Control {ctrl.get('acronym')} missing naJustification"
    if status == "Manually Inherited":
        inherited_missing = ["commonControlProvider"] + [
            field for field in _SLCM_REQUIRED if not ctrl.get(field)
        ]
        inherited_missing = [field for field in inherited_missing if not ctrl.get(field)]
        if inherited_missing:
            return (
                f"Control {ctrl.get('acronym')} missing inherited fields: "
                f"{', '.join(inherited_missing)}"
            )
    return None


@router.put("/systems/{system_id}/controls")
async def update_controls(system_id: int, payload: list[dict[str, Any]]):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    for ctrl in payload:
        message = _validate_control(ctrl)
        if message:
            return error(400, message)

    failures = get_failures()
    data: list[dict[str, Any]] = []

    for ctrl in payload:
        acronym = str(ctrl.get("acronym") or "").strip()
        item: dict[str, Any] = {
            "acronym": acronym,
            "systemId": system_id,
            "success": True,
        }

        injected = failures.control_status.get(acronym.upper())
        if injected is not None and injected >= 400:
            item["success"] = False
            item["errors"] = [
                {
                    "code": str(injected),
                    "message": f"Injected failure ({injected}) for {acronym}",
                }
            ]
            data.append(item)
            continue

        record.controls[acronym] = {**ctrl, "systemId": system_id}
        data.append(item)

    return ok(data)


@router.get("/systems/{system_id}/controls")
async def list_controls(system_id: int, request: Request):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    # If we have state, serve it. Empty state returns [] deterministically.
    return ok(list(record.controls.values()))
