"""Admin routes under /_admin — not part of the real eMASS API.

Used by tests and operators to reset state, inject failures, seed the
assessment-procedure table, and read back what the mock received (uploaded
bytes, scan uploads) without polluting the spec-shaped public responses.
These routes bypass failure-injection middleware so the mock is always
controllable.
"""

from __future__ import annotations

import base64
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

from ..config import load_settings
from ..failures import get_failures
from ..spec import (
    catalog,
    example_body,
    normalize_path_template,
    operation,
    spec_version,
    unknown_fields_rejected,
    validate_request,
)
from ..store import get_store
from ..traffic import entry_dict, get_traffic

router = APIRouter(prefix="/_admin", tags=["admin"])


class ValidateRequest(BaseModel):
    operationId: str
    body: Any = None


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


def stateful_routes(app: Any) -> set[tuple[str, str]]:
    """(METHOD, normalized path) pairs the mock answers itself instead of proxying.

    Read from the routers the app registered (``app.state.emass_routers``),
    not ``app.routes``: recent FastAPI wraps included routers lazily, so their
    endpoints do not appear there.
    """
    found: set[tuple[str, str]] = set()
    for emass_router in getattr(app.state, "emass_routers", ()):
        for route in emass_router.routes:
            if isinstance(route, APIRoute):
                for method in route.methods or ():
                    found.add((method, normalize_path_template(route.path)))
    return found


@router.get("/failures")
async def get_failure_config() -> dict[str, Any]:
    f = get_failures()
    return {
        "global_status": f.global_status,
        "path_status": dict(f.path_status),
        "control_status": dict(f.control_status),
        "artifact_filename_status": dict(f.artifact_filename_status),
        "artifact_force_empty": f.artifact_force_empty,
        "latency_seconds": f.latency_seconds,
    }


@router.get("/settings")
async def get_settings() -> dict[str, Any]:
    settings = load_settings()
    return {
        "spec_version": spec_version(),
        "api_key": settings.api_key,
        "require_api_key": settings.require_api_key,
        "require_user_uid_on_all": settings.require_user_uid_on_all,
        "unknown_fields": "reject" if unknown_fields_rejected() else "allow",
        "prism_url": settings.prism_url,
        "systems": [s.system_id for s in get_store().list_systems()],
        "traffic_limit": get_traffic().limit,
    }


@router.get("/operations")
async def list_operations(request: Request) -> list[dict[str, Any]]:
    """Every spec operation, flagged ``stateful`` when the mock answers it itself."""
    handled = stateful_routes(request.app)
    return [
        {**entry, "stateful": (entry["method"], normalize_path_template(entry["path"])) in handled}
        for entry in catalog()
    ]


@router.get("/operations/{operation_id}/example")
async def operation_example(
    operation_id: str, mode: str = Query(default="required", pattern="^(required|full)$")
) -> Any:
    try:
        operation(operation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"operationId": operation_id, "mode": mode, "body": example_body(operation_id, mode)}


@router.post("/validate")
async def validate_body(payload: ValidateRequest) -> dict[str, Any]:
    """Check a JSON body against an operation without sending it."""
    try:
        operation(payload.operationId)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    errors = validate_request(payload.operationId, payload.body)
    return {"operationId": payload.operationId, "valid": not errors, "errors": errors}


@router.get("/requests")
async def list_requests(
    after: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500)
) -> dict[str, Any]:
    log = get_traffic()
    entries = log.list(after=after, limit=limit)
    return {
        "entries": [e.summary() for e in entries],
        "limit": log.limit,
        "cursor": entries[-1].cursor if entries else after,
    }


@router.get("/requests/{entry_id}")
async def get_request(entry_id: int) -> dict[str, Any]:
    entry = get_traffic().get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Request {entry_id} is not in the log")
    return entry_dict(entry)


@router.delete("/requests")
async def clear_requests() -> dict[str, Any]:
    get_traffic().clear()
    return {"status": "ok"}


@router.get("/systems/{system_id}/artifacts/{index}/content")
async def artifact_content(system_id: int, index: int) -> Response:
    """The exact bytes an artifact upload delivered, as a download."""
    artifacts = _system(system_id).artifacts
    if index < 0 or index >= len(artifacts):
        raise HTTPException(status_code=404, detail=f"Artifact {index} not found")
    art = artifacts[index]
    content = base64.b64decode(art.get("_content_b64", ""))
    filename = art.get("filename") or f"artifact-{index}"
    quoted_filename = quote(filename, safe="")
    disposition = (
        f"attachment; filename*=utf-8''{quoted_filename}"
        if quoted_filename != filename
        else f'attachment; filename="{filename}"'
    )
    return Response(
        content=content,
        media_type=art.get("mimeContentType") or "application/octet-stream",
        headers={"content-disposition": disposition},
    )
