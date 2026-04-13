"""Admin routes under /_admin — not part of the real eMASS API.

Used by tests and operators to reset state and inject failures. These routes
bypass failure-injection middleware so the mock is always controllable.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import load_settings
from ..failures import get_failures
from ..store import get_store

router = APIRouter(prefix="/_admin", tags=["admin"])


class FailureUpdate(BaseModel):
    global_status: int | None = None
    path_status: dict[str, int] = Field(default_factory=dict)
    control_status: dict[str, int] = Field(default_factory=dict)
    latency_seconds: float = 0.0


@router.post("/reset")
async def reset_all() -> dict[str, Any]:
    settings = load_settings()
    get_store().reset(settings.seed_system_ids)
    get_failures().reset()
    return {"status": "ok", "seeded_systems": list(settings.seed_system_ids)}


@router.get("/state")
async def dump_state() -> dict[str, Any]:
    store = get_store()
    return {
        "systems": [
            {
                "systemId": s.system_id,
                "controls": len(s.controls),
                "test_results": len(s.test_results),
                "artifacts": len(s.artifacts),
                "poams": len(s.poams),
            }
            for s in store.list_systems()
        ],
        "failures": {
            "global_status": get_failures().global_status,
            "path_status": dict(get_failures().path_status),
            "control_status": dict(get_failures().control_status),
            "latency_seconds": get_failures().latency_seconds,
        },
    }


@router.post("/failures")
async def set_failures(update: FailureUpdate) -> dict[str, Any]:
    f = get_failures()
    f.global_status = update.global_status
    f.path_status = dict(update.path_status)
    f.control_status = {k.upper(): v for k, v in update.control_status.items()}
    f.latency_seconds = update.latency_seconds
    return {"status": "ok"}


@router.delete("/failures")
async def clear_failures() -> dict[str, Any]:
    get_failures().reset()
    return {"status": "ok"}
