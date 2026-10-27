"""Admin routes under /_admin — not part of the real eMASS API.

Used by tests and operators to reset state, inject failures, seed the
assessment-procedure table, and read back what the mock received (uploaded
bytes, scan uploads) without polluting the spec-shaped public responses.
These routes bypass failure-injection middleware so the mock is always
controllable.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import load_settings
from ..failures import get_failures
from ..spec import spec_version
from ..store import get_store

router = APIRouter(prefix="/_admin", tags=["admin"])


class FailureUpdate(BaseModel):
    global_status: int | None = None
    path_status: dict[str, int] = Field(default_factory=dict)
    control_status: dict[str, int] = Field(default_factory=dict)
    artifact_filename_status: dict[str, int] = Field(default_factory=dict)
    artifact_force_empty: bool = False
    latency_seconds: float = 0.0


def _system(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"System {system_id} not found")
    return record


@router.post("/reset")
async def reset_all() -> dict[str, Any]:
    settings = load_settings()
    get_store().reset(settings.seed_system_ids, settings.seed_assessment_procedures)
    get_failures().reset()
    return {"status": "ok", "seeded_systems": list(settings.seed_system_ids)}


@router.get("/state")
async def dump_state() -> dict[str, Any]:
    store = get_store()
    failures = get_failures()
    return {
        "spec_version": spec_version(),
        "systems": [
            {
                "systemId": s.system_id,
                "controls": len(s.controls),
                "test_results": len(s.test_results),
                "artifacts": len(s.artifacts),
                "poams": len(s.poams),
                "milestones": sum(len(p["milestones"]) for p in s.poams),
                "hardware": len(s.hardware),
                "software": len(s.software),
                "device_scans": len(s.device_scans),
                "assessment_procedures": len(s.assessment_procedures),
            }
            for s in store.list_systems()
        ],
        "failures": {
            "global_status": failures.global_status,
            "path_status": dict(failures.path_status),
            "control_status": dict(failures.control_status),
            "artifact_filename_status": dict(failures.artifact_filename_status),
            "artifact_force_empty": failures.artifact_force_empty,
            "latency_seconds": failures.latency_seconds,
        },
    }


@router.post("/failures")
async def set_failures(update: FailureUpdate) -> dict[str, Any]:
    f = get_failures()
    f.global_status = update.global_status
    f.path_status = dict(update.path_status)
    f.control_status = {k.upper(): v for k, v in update.control_status.items()}
    f.artifact_filename_status = dict(update.artifact_filename_status)
    f.artifact_force_empty = update.artifact_force_empty
    f.latency_seconds = update.latency_seconds
    return {"status": "ok"}


@router.delete("/failures")
async def clear_failures() -> dict[str, Any]:
    get_failures().reset()
    return {"status": "ok"}


@router.get("/systems/{system_id}/assessment-procedures")
async def list_assessment_procedures(system_id: int) -> dict[str, str]:
    return dict(_system(system_id).assessment_procedures)


@router.post("/systems/{system_id}/assessment-procedures")
async def seed_assessment_procedures(system_id: int, table: dict[str, str]) -> dict[str, Any]:
    """Merge ``{"AC-1.1": "000001", ...}`` into the system's procedure table."""
    record = _system(system_id)
    record.assessment_procedures.update({k.strip(): v.strip() for k, v in table.items()})
    return {"status": "ok", "assessment_procedures": len(record.assessment_procedures)}


@router.get("/systems/{system_id}/artifacts")
async def raw_artifacts(system_id: int) -> list[dict[str, Any]]:
    """Stored artifacts including the uploaded bytes (``_content_b64``) and ``_part_name``."""
    return list(_system(system_id).artifacts)


@router.get("/systems/{system_id}/device-scans")
async def raw_device_scans(system_id: int) -> list[dict[str, Any]]:
    return list(_system(system_id).device_scans)
