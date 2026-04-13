"""POST /api/systems/{systemId}/test-results — stateful handler.

Response shape matches MITRE spec `TestResultsResponsePost`:
    {"meta": {"code": 200}, "data": [TestResultsPost, ...]}
Each `TestResultsPost` row echoes the submitted test result plus a
server-generated `testResultId` and `success` flag.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..auth import require_api_key
from ..envelope import error, ok
from ..store import get_store

router = APIRouter(prefix="/api", tags=["test-results"], dependencies=[Depends(require_api_key)])


@router.post("/systems/{system_id}/test-results")
async def submit_test_results(system_id: int, payload: list[dict[str, Any]]):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    data: list[dict[str, Any]] = []
    for tr in payload:
        stored = {**tr, "systemId": system_id}
        record.test_results.append(stored)
        # testResultId is server-assigned in real eMASS; synthesize a stable one.
        test_result_id = len(record.test_results)
        data.append(
            {
                "cci": tr.get("cci"),
                "systemId": system_id,
                "testedBy": tr.get("testedBy"),
                "testDate": tr.get("testDate"),
                "description": tr.get("description"),
                "complianceStatus": tr.get("complianceStatus"),
                "testResultId": test_result_id,
                "success": True,
            }
        )
    return ok(data)


@router.get("/systems/{system_id}/test-results")
async def list_test_results(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return ok(record.test_results)
