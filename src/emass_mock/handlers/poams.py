"""POST, PUT, DELETE and GET /api/systems/{systemId}/poams (+ /poams/{poamId}).

Request bodies are validated against ``PoamRequestPostBody``,
``PoamRequestPutBody`` and ``PoamRequestDeleteBody``. Write responses are
``PoamPostPutDel`` rows: ``{"systemId", "poamId", "externalUid"?, "success",
"errors"?}``. ``poamId`` and ``displayPoamId`` are server-assigned.

Nested ``milestones`` on POST get ids assigned. On PUT the nested list is
treated as the new list; a milestone whose description matches an existing
one keeps its id, anything else gets a fresh id (the spec's nested PUT shape
carries no ``milestoneId``, so there is nothing better to match on).

GET (``getSystemPoams``) honours ``controlAcronyms`` and the spec's
``systemOnly`` parameter, which **defaults to true**: a bare GET returns only
system-level POA&Ms (no ``controlAcronym`` and no ``assessmentProcedure``).
Pass ``systemOnly=false`` to read control-level items back.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..auth import require_emu_auth
from ..envelope import error, ok, row_errors
from ..store import SystemRecord
from ._common import JSON_BODY, csv_param, reject_invalid_body, system_or_404

OPERATION_POST = "addPoamBySystemId"
OPERATION_PUT = "updatePoamBySystemId"
OPERATION_DELETE = "deletePoam"
OPERATION_GET = "getSystemPoams"
OPERATION_GET_ONE = "getSystemPoamsByPoamId"

router = APIRouter(prefix="/api", tags=["poams"], dependencies=[Depends(require_emu_auth)])


def new_milestone(
    record: SystemRecord, poam_id: int, body: dict[str, Any], milestone_id: int | None = None
) -> dict[str, Any]:
    """A stored milestone in ``MilestonesGet`` shape."""
    return {
        "systemId": record.system_id,
        "poamId": poam_id,
        "milestoneId": milestone_id or record.next_milestone_id(),
        "description": body["description"],
        "scheduledCompletionDate": body["scheduledCompletionDate"],
        "reviewStatus": "Not Approved",
        "createdBy": "emass-mock",
        "createdDate": int(time.time()),
    }


def _result_row(system_id: int, poam: dict[str, Any], poam_id: int | None) -> dict[str, Any]:
    row: dict[str, Any] = {"systemId": system_id}
    if poam_id is not None:
        row["poamId"] = poam_id
    if poam.get("externalUid") is not None:
        row["externalUid"] = poam["externalUid"]
    row["success"] = True
    return row


@router.post("/systems/{system_id}/poams")
async def create_poams(system_id: int, payload: Any = JSON_BODY):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record
    rejected = reject_invalid_body(OPERATION_POST, payload)
    if rejected is not None:
        return rejected

    data: list[dict[str, Any]] = []
    for poam in payload:
        poam_id = record.next_poam_id()
        milestones = [new_milestone(record, poam_id, m) for m in poam.get("milestones") or []]
        stored = {
            **{k: v for k, v in poam.items() if k != "milestones"},
            "systemId": system_id,
            "poamId": poam_id,
            "displayPoamId": record.display_poam_id(poam_id),
            "milestones": milestones,
            "reviewStatus": "Not Approved",
            "isInherited": False,
            "createdDate": int(time.time()),
        }
        record.poams.append(stored)
        data.append(_result_row(system_id, poam, poam_id))
    return ok(data)


@router.put("/systems/{system_id}/poams")
async def update_poams(system_id: int, payload: Any = JSON_BODY):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record
    rejected = reject_invalid_body(OPERATION_PUT, payload)
    if rejected is not None:
        return rejected

    data: list[dict[str, Any]] = []
    for poam in payload:
        poam_id = poam["poamId"]
        target = record.find_poam(poam_id)
        if target is None:
            row = _result_row(system_id, poam, poam_id)
            row["success"] = False
            row["errors"] = row_errors(f"poamId: {poam_id} not found on system {system_id}")
            data.append(row)
            continue
        if "milestones" in poam:
            by_description = {m["description"]: m["milestoneId"] for m in target["milestones"]}
            target["milestones"] = [
                new_milestone(record, poam_id, m, by_description.get(m["description"]))
                for m in poam["milestones"] or []
            ]
        for key, value in poam.items():
            if key not in {"poamId", "displayPoamId", "systemId", "milestones"}:
                target[key] = value
        data.append(_result_row(system_id, poam, poam_id))
    return ok(data)


@router.delete("/systems/{system_id}/poams")
async def delete_poams(system_id: int, payload: Any = JSON_BODY):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record
    rejected = reject_invalid_body(OPERATION_DELETE, payload)
    if rejected is not None:
        return rejected

    data: list[dict[str, Any]] = []
    for item in payload:
        poam_id = item.get("poamId")
        target = record.find_poam(poam_id) if poam_id is not None else None
        row: dict[str, Any] = {"systemId": system_id}
        if poam_id is not None:
            row["poamId"] = poam_id
        if target is None:
            row["success"] = False
            row["errors"] = row_errors(f"poamId: {poam_id} not found on system {system_id}")
        else:
            record.poams.remove(target)
            row["success"] = True
        data.append(row)
    return ok(data)


@router.get("/systems/{system_id}/poams")
async def list_poams(
    system_id: int,
    controlAcronyms: str | None = Query(default=None),
    systemOnly: bool = Query(default=True),
):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record
    wanted = csv_param(controlAcronyms)
    rows = []
    for poam in record.poams:
        acronym = (poam.get("controlAcronym") or "").upper()
        if systemOnly and (acronym or poam.get("assessmentProcedure")):
            continue
        if wanted and acronym not in wanted:
            continue
        rows.append(poam)
    return ok(rows)


@router.get("/systems/{system_id}/poams/{poam_id}")
async def get_poam(system_id: int, poam_id: int):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record
    target = record.find_poam(poam_id)
    if target is None:
        return error(404, f"POA&M {poam_id} not found on system {system_id}")
    return ok(target)
