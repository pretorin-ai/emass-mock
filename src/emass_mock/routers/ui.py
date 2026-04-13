"""Inspector UI at /ui — not part of the real eMASS surface.

Renders a small HTMX-powered dashboard over the in-memory store and
failure-injection config. Intended for local debugging and demos.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..failures import get_failures
from ..store import get_store

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/ui", tags=["ui"], include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    systems = get_store().list_systems()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"systems": systems, "failures": get_failures()},
    )


@router.get("/systems/{system_id}", response_class=HTMLResponse)
async def system_detail(request: Request, system_id: int) -> HTMLResponse:
    record = get_store().get_system(system_id)
    if record is None:
        return HTMLResponse(f"System {system_id} not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "system.html",
        {"system": record},
    )


@router.post("/failures")
async def update_failures(
    global_status: str = Form(default=""),
    control_acronym: str = Form(default=""),
    control_status: str = Form(default=""),
    latency_seconds: str = Form(default="0"),
) -> RedirectResponse:
    f = get_failures()
    f.global_status = int(global_status) if global_status.strip() else None
    if control_acronym.strip() and control_status.strip():
        f.control_status[control_acronym.strip().upper()] = int(control_status)
    try:
        f.latency_seconds = float(latency_seconds)
    except ValueError:
        f.latency_seconds = 0.0
    return RedirectResponse(url="/ui/", status_code=303)


@router.post("/failures/clear")
async def clear_failures_ui() -> RedirectResponse:
    get_failures().reset()
    return RedirectResponse(url="/ui/", status_code=303)


@router.post("/reset")
async def reset_ui(request: Request) -> RedirectResponse:
    from ..config import load_settings

    get_store().reset(load_settings().seed_system_ids)
    get_failures().reset()
    return RedirectResponse(url="/ui/", status_code=303)
