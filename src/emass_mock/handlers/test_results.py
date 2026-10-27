"""POST and GET /api/systems/{systemId}/test-results.

POST (``addTestResultsBySystemId``) takes ``TestResultsRequestPostBody``: rows
of ``testedBy, testDate, description, complianceStatus, assessmentProcedure``.
There is no ``cci`` in the request. eMASS keys a test result by its
assessment procedure (``AC-1.1`` style) and reports the matching CCI back in
the ``TestResultsPost`` row: ``{"cci", "success", "systemId", "errors"?}``.

The mock resolves the CCI from the system's assessment-procedure table. An
unknown procedure fails per row, which is also how a caller discovers that it
is sending control ids or STIG rule ids where eMASS wants procedure ids.

GET (``getSystemTestResults``) returns ``TestResultsGet`` rows and honours the
spec's filters: ``controlAcronyms``, ``assessmentProcedures``, ``ccis`` (all
comma-separated) and ``latestOnly``, which the spec defaults to ``true``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..auth import require_emu_auth
from ..envelope import ok, row_errors
from ._common import JSON_BODY, csv_param, reject_invalid_body, system_or_404

OPERATION_POST = "addTestResultsBySystemId"
OPERATION_GET = "getSystemTestResults"

# ``TestResultsGet.complianceStatus`` enum. The request schema leaves the
# string open, so this is enforced as a per-row business rule.
COMPLIANCE_STATUSES = ("Compliant", "Non-Compliant", "Not Applicable")

router = APIRouter(prefix="/api", tags=["test-results"], dependencies=[Depends(require_emu_auth)])


def _normalize_cci(value: str) -> str:
    return value.strip().upper().removeprefix("CCI-")


@router.post("/systems/{system_id}/test-results")
async def submit_test_results(system_id: int, payload: Any = JSON_BODY):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record
    rejected = reject_invalid_body(OPERATION_POST, payload)
    if rejected is not None:
        return rejected

    data: list[dict[str, Any]] = []
    for tr in payload:
        procedure = str(tr["assessmentProcedure"]).strip()
        cci = record.assessment_procedures.get(procedure)
        row: dict[str, Any] = {"systemId": system_id, "success": True}
        problems: list[str] = []
        if cci is None:
            problems.append(
                f"assessmentProcedure: {procedure} is not an assessment procedure on "
                f"system {system_id}"
            )
        else:
            row["cci"] = cci
        if tr["complianceStatus"] not in COMPLIANCE_STATUSES:
            problems.append("complianceStatus: must be one of " + ", ".join(COMPLIANCE_STATUSES))
        if problems:
            row["success"] = False
            row["errors"] = row_errors(*problems)
            data.append(row)
            continue

        record.test_results.append(
            {
                "systemId": system_id,
                "control": procedure.split(".", 1)[0],
                "cci": cci,
                "assessmentProcedure": procedure,
                "isInherited": False,
                "testedBy": tr["testedBy"],
                "testDate": tr["testDate"],
                "description": tr["description"],
                "type": None,
                "complianceStatus": tr["complianceStatus"],
            }
        )
        data.append(row)
    return ok(data)


@router.get("/systems/{system_id}/test-results")
async def list_test_results(
    system_id: int,
    controlAcronyms: str | None = Query(default=None),
    assessmentProcedures: str | None = Query(default=None),
    ccis: str | None = Query(default=None),
    latestOnly: bool = Query(default=True),
):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record

    controls = csv_param(controlAcronyms)
    procedures = csv_param(assessmentProcedures)
    wanted_ccis = {_normalize_cci(c) for c in csv_param(ccis)}

    rows = [
        tr
        for tr in record.test_results
        if (not controls or tr["control"].upper() in controls)
        and (not procedures or tr["assessmentProcedure"].upper() in procedures)
        and (not wanted_ccis or _normalize_cci(tr["cci"]) in wanted_ccis)
    ]
    if latestOnly:
        latest: dict[str, dict[str, Any]] = {}
        for tr in rows:
            key = tr["assessmentProcedure"]
            if key not in latest or tr["testDate"] >= latest[key]["testDate"]:
                latest[key] = tr
        rows = list(latest.values())
    return ok(rows)
