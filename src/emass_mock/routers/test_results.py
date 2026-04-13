"""POST /api/systems/{system_id}/test-results — submit test results."""

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
    record.test_results.extend(payload)
    return ok([{"status": "accepted"} for _ in payload])


@router.get("/systems/{system_id}/test-results")
async def list_test_results(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return ok(record.test_results)
