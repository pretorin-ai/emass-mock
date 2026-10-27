"""/api/systems/{systemId}/poams/{poamId}/milestones and /milestones/{milestoneId}.

GET, POST, PUT and DELETE on the collection, GET on one milestone. Bodies are
validated against ``MilestonesRequestPostBody`` / ``PutBody`` / ``DeleteBody``;
write responses are ``MilestonesPutPostDelete`` rows:
``{"systemId", "poamId", "milestoneId", "success", "errors"?}``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth import require_emu_auth
from ..envelope import error, ok, row_errors
from ._common import JSON_BODY, reject_invalid_body, system_or_404
from .poams import new_milestone

OPERATION_GET = "getSystemMilestonesByPoamId"
OPERATION_GET_ONE = "getSystemMilestonesByPoamIdAndMilestoneId"
OPERATION_POST = "addMilestoneBySystemIdAndPoamId"
OPERATION_PUT = "updateMilestoneBySystemIdAndPoamId"
OPERATION_DELETE = "deleteMilestone"

router = APIRouter(prefix="/api", tags=["milestones"], dependencies=[Depends(require_emu_auth)])


def _poam_or_404(system_id: int, poam_id: int):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record, None
    poam = record.find_poam(poam_id)
    if poam is None:
        return error(404, f"POA&M {poam_id} not found on system {system_id}"), None
    return record, poam


def _row(system_id: int, poam_id: int, milestone_id: int | None, *errors: str) -> dict[str, Any]:
    row: dict[str, Any] = {"systemId": system_id, "poamId": poam_id}
    if milestone_id is not None:
        row["milestoneId"] = milestone_id
    if errors:
        row["success"] = False
        row["errors"] = row_errors(*errors)
    else:
        row["success"] = True
    return row


@router.get("/systems/{system_id}/poams/{poam_id}/milestones")
async def list_milestones(system_id: int, poam_id: int):
    record, poam = _poam_or_404(system_id, poam_id)
    if poam is None:
        return record
    return ok(list(poam["milestones"]))


@router.post("/systems/{system_id}/poams/{poam_id}/milestones")
async def add_milestones(system_id: int, poam_id: int, payload: Any = JSON_BODY):
    record, poam = _poam_or_404(system_id, poam_id)
    if poam is None:
        return record
    rejected = reject_invalid_body(OPERATION_POST, payload)
    if rejected is not None:
        return rejected
    data = []
    for body in payload:
        milestone = new_milestone(record, poam_id, body)
        poam["milestones"].append(milestone)
        data.append(_row(system_id, poam_id, milestone["milestoneId"]))
    return ok(data)


@router.put("/systems/{system_id}/poams/{poam_id}/milestones")
async def update_milestones(system_id: int, poam_id: int, payload: Any = JSON_BODY):
    record, poam = _poam_or_404(system_id, poam_id)
    if poam is None:
        return record
    rejected = reject_invalid_body(OPERATION_PUT, payload)
    if rejected is not None:
        return rejected
    data = []
    for body in payload:
        milestone_id = body["milestoneId"]
        target = next((m for m in poam["milestones"] if m["milestoneId"] == milestone_id), None)
        if target is None:
            data.append(
                _row(
                    system_id,
                    poam_id,
                    milestone_id,
                    f"milestoneId: {milestone_id} not found on POA&M {poam_id}",
                )
            )
            continue
        target["description"] = body["description"]
        target["scheduledCompletionDate"] = body["scheduledCompletionDate"]
        data.append(_row(system_id, poam_id, milestone_id))
    return ok(data)


@router.delete("/systems/{system_id}/poams/{poam_id}/milestones")
async def delete_milestones(system_id: int, poam_id: int, payload: Any = JSON_BODY):
    record, poam = _poam_or_404(system_id, poam_id)
    if poam is None:
        return record
    rejected = reject_invalid_body(OPERATION_DELETE, payload)
    if rejected is not None:
        return rejected
    data = []
    for body in payload:
        milestone_id = body.get("milestoneId")
        target = next((m for m in poam["milestones"] if m["milestoneId"] == milestone_id), None)
        if target is None:
            data.append(
                _row(
                    system_id,
                    poam_id,
                    milestone_id,
                    f"milestoneId: {milestone_id} not found on POA&M {poam_id}",
                )
            )
            continue
        poam["milestones"].remove(target)
        data.append(_row(system_id, poam_id, milestone_id))
    return ok(data)


@router.get("/systems/{system_id}/poams/{poam_id}/milestones/{milestone_id}")
async def get_milestone(system_id: int, poam_id: int, milestone_id: int):
    record, poam = _poam_or_404(system_id, poam_id)
    if poam is None:
        return record
    target = next((m for m in poam["milestones"] if m["milestoneId"] == milestone_id), None)
    if target is None:
        return error(404, f"Milestone {milestone_id} not found on POA&M {poam_id}")
    return ok(target)
