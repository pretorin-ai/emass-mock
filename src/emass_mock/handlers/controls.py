"""PUT and GET /api/systems/{systemId}/controls.

PUT (``updateControlBySystemId``) validates the body against
``ControlsRequestPutBody`` and answers with one ``ControlsPut`` row per
submitted control: ``{"acronym", "success", "systemId", "errors"?}``.

Two kinds of failure, mirroring how eMASS reports them:

* A body that does not match the schema (missing required field, wrong enum,
  unknown field) is a 400 for the whole batch.
* The spec's "[Conditional]" rules cannot be expressed in the schema, so they
  fail per row with ``success: false`` and an ``errors`` array of strings.

Per-item failures can also be injected through the admin API (acronym to
status code).

GET (``getSystemControls``) serves what was stored, filtered by the
comma-separated ``acronyms`` query parameter, and adds the read-only ``ccis``
field from the system's assessment-procedure table.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..auth import require_emu_auth
from ..envelope import ok, row_errors
from ..failures import get_failures
from ._common import JSON_BODY, csv_param, reject_invalid_body, system_or_404

OPERATION_PUT = "updateControlBySystemId"
OPERATION_GET = "getSystemControls"

router = APIRouter(prefix="/api", tags=["controls"], dependencies=[Depends(require_emu_auth)])

_SLCM_FIELDS = (
    "slcmCriticality",
    "slcmFrequency",
    "slcmMethod",
    "slcmReporting",
    "slcmTracking",
    "slcmComments",
)


def _conditional_errors(ctrl: dict[str, Any]) -> list[str]:
    """Rules from the spec's ``[Conditional]`` field descriptions."""
    problems: list[str] = []
    status = ctrl.get("implementationStatus")
    if status in {"Planned", "Implemented"}:
        problems += [
            f"{field}: required when implementationStatus is {status}"
            for field in _SLCM_FIELDS
            if not ctrl.get(field)
        ]
    elif status == "Not Applicable":
        if not ctrl.get("naJustification"):
            problems.append("naJustification: required when implementationStatus is Not Applicable")
    elif status == "Manually Inherited":
        if not ctrl.get("commonControlProvider"):
            problems.append(
                "commonControlProvider: required when implementationStatus is Manually Inherited"
            )
        problems += [
            f"{field}: required when implementationStatus is Manually Inherited"
            for field in _SLCM_FIELDS
            if not ctrl.get(field)
        ]
    return problems


@router.put("/systems/{system_id}/controls")
async def update_controls(system_id: int, payload: Any = JSON_BODY):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record
    rejected = reject_invalid_body(OPERATION_PUT, payload)
    if rejected is not None:
        return rejected

    failures = get_failures()
    data: list[dict[str, Any]] = []
    for ctrl in payload:
        acronym = str(ctrl["acronym"]).strip()
        row: dict[str, Any] = {"acronym": acronym, "systemId": system_id, "success": True}

        injected = failures.control_status.get(acronym.upper())
        if injected is not None and injected >= 400:
            row["success"] = False
            row["errors"] = row_errors(f"acronym: injected failure ({injected}) for {acronym}")
            data.append(row)
            continue

        problems = _conditional_errors(ctrl)
        if problems:
            row["success"] = False
            row["errors"] = row_errors(*problems)
            data.append(row)
            continue

        record.controls[acronym] = {**ctrl, "acronym": acronym, "systemId": system_id}
        data.append(row)
    return ok(data)


@router.get("/systems/{system_id}/controls")
async def list_controls(system_id: int, acronyms: str | None = Query(default=None)):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record
    wanted = csv_param(acronyms)
    rows = []
    for acronym, ctrl in record.controls.items():
        if wanted and acronym.upper() not in wanted:
            continue
        ccis = record.ccis_for_control(acronym)
        rows.append({**ctrl, "ccis": ",".join(ccis) if ccis else None})
    return ok(rows)
