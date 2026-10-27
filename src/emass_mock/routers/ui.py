"""Testing UI at /ui — not part of the real eMASS surface.

Server-rendered pages plus two small scripts (no build step, no CDN):

* ``/ui/``          dashboard: settings, systems, recent requests
* ``/ui/console``   compose and send any spec operation, with examples
                    generated from the spec and validation before sending
* ``/ui/traffic``   live log of every ``/api`` request the mock received
* ``/ui/systems/N`` everything stored for a system, procedure table editing
* ``/ui/failures``  every failure-injection knob

Writes go through plain HTML forms that post back here and redirect, so the
pages work without JavaScript except for the console and the live log.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import load_settings
from ..failures import get_failures
from ..spec import spec_version, unknown_fields_rejected
from ..store import SystemRecord, get_store
from ..traffic import get_traffic

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/ui", tags=["ui"], include_in_schema=False)

RULE_KINDS = {
    "control": "control_status",
    "path": "path_status",
    "artifact_suffix": "artifact_filename_status",
}


def _context(request: Request, active: str, **extra: Any) -> dict[str, Any]:
    settings = load_settings()
    failures = get_failures()
    active_failures = (
        (1 if failures.global_status is not None else 0)
        + len(failures.path_status)
        + len(failures.control_status)
        + len(failures.artifact_filename_status)
        + (1 if failures.artifact_force_empty else 0)
        + (1 if failures.latency_seconds > 0 else 0)
    )
    return {
        "request": request,
        "active": active,
        "spec_version": spec_version(),
        "settings": settings,
        "unknown_fields": "reject" if unknown_fields_rejected() else "allow",
        "failures": failures,
        "active_failures": active_failures,
        **extra,
    }


def _counts(record: SystemRecord) -> dict[str, int]:
    return {
        "controls": len(record.controls),
        "test_results": len(record.test_results),
        "poams": len(record.poams),
        "milestones": sum(len(p.get("milestones") or []) for p in record.poams),
        "artifacts": len(record.artifacts),
        "hardware": len(record.hardware),
        "software": len(record.software),
        "device_scans": len(record.device_scans),
        "procedures": len(record.assessment_procedures),
    }


def _back(request: Request, fallback: str) -> RedirectResponse:
    target = request.headers.get("referer") or fallback
    # Only follow same-site referers back into the UI.
    if "/ui/" not in target:
        target = fallback
    return RedirectResponse(url=target, status_code=303)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    systems = [(s, _counts(s)) for s in get_store().list_systems()]
    recent = list(reversed(get_traffic().list(limit=10)))
    return templates.TemplateResponse(
        request, "index.html", _context(request, "dashboard", systems=systems, recent=recent)
    )


@router.get("/console", response_class=HTMLResponse)
async def console(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "console.html", _context(request, "console"))


@router.get("/traffic", response_class=HTMLResponse)
async def traffic(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "traffic.html", _context(request, "traffic", traffic_limit=get_traffic().limit)
    )


@router.get("/failures", response_class=HTMLResponse)
async def failures_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "failures.html", _context(request, "failures"))


@router.get("/systems/{system_id}", response_class=HTMLResponse)
async def system_detail(request: Request, system_id: int) -> HTMLResponse:
    record = get_store().get_system(system_id)
    if record is None:
        return HTMLResponse(f"System {system_id} not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "system.html",
        _context(request, "systems", system=record, counts=_counts(record)),
    )


@router.post("/failures/global")
async def update_global_failures(
    request: Request,
    global_status: str = Form(default=""),
    latency_seconds: str = Form(default="0"),
    artifact_force_empty: str = Form(default=""),
) -> RedirectResponse:
    f = get_failures()
    f.global_status = int(global_status) if global_status.strip() else None
    try:
        f.latency_seconds = max(0.0, float(latency_seconds or 0))
    except ValueError:
        f.latency_seconds = 0.0
    f.artifact_force_empty = artifact_force_empty == "on"
    return _back(request, "/ui/failures")


@router.post("/failures/rule")
async def add_failure_rule(
    request: Request,
    kind: str = Form(...),
    key: str = Form(...),
    status: int = Form(...),
) -> RedirectResponse:
    attr = RULE_KINDS.get(kind)
    key = key.strip()
    if attr and key:
        if kind == "control":
            key = key.upper()
        getattr(get_failures(), attr)[key] = status
    return _back(request, "/ui/failures")


@router.post("/failures/rule/delete")
async def delete_failure_rule(
    request: Request, kind: str = Form(...), key: str = Form(...)
) -> RedirectResponse:
    attr = RULE_KINDS.get(kind)
    if attr:
        getattr(get_failures(), attr).pop(key, None)
    return _back(request, "/ui/failures")


@router.post("/failures/clear")
async def clear_failures_ui(request: Request) -> RedirectResponse:
    get_failures().reset()
    return _back(request, "/ui/failures")


@router.post("/reset")
async def reset_ui(request: Request) -> RedirectResponse:
    settings = load_settings()
    get_store().reset(settings.seed_system_ids, settings.seed_assessment_procedures)
    get_failures().reset()
    return _back(request, "/ui/")


@router.post("/traffic/clear")
async def clear_traffic_ui(request: Request) -> RedirectResponse:
    get_traffic().clear()
    return _back(request, "/ui/traffic")


@router.post("/systems/{system_id}/assessment-procedures")
async def add_procedure(
    request: Request,
    system_id: int,
    procedure: str = Form(...),
    cci: str = Form(...),
) -> RedirectResponse:
    record = get_store().get_system(system_id)
    procedure, cci = procedure.strip(), cci.strip().upper().removeprefix("CCI-")
    if record is not None and procedure and cci:
        record.assessment_procedures[procedure] = cci
    return _back(request, f"/ui/systems/{system_id}")


@router.post("/systems/{system_id}/assessment-procedures/delete")
async def delete_procedure(
    request: Request, system_id: int, procedure: str = Form(...)
) -> RedirectResponse:
    record = get_store().get_system(system_id)
    if record is not None:
        record.assessment_procedures.pop(procedure, None)
    return _back(request, f"/ui/systems/{system_id}")
