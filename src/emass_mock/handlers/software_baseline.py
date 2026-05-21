"""Software Baseline endpoints. Mirrors hardware_baseline.py shape."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..auth import require_emu_auth
from ..envelope import error, ok
from ..store import get_store

router = APIRouter(
    prefix="/api",
    tags=["software-baseline"],
    dependencies=[Depends(require_emu_auth)],
)


REQUIRED_SW_FIELDS = ("softwareVendor", "softwareName", "version")


def _missing_required(item: dict[str, Any]) -> list[str]:
    return [f for f in REQUIRED_SW_FIELDS if not item.get(f)]


@router.get("/systems/{system_id}/sw-baseline")
async def get_software_baseline(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return ok(list(record.software.values()))


@router.post("/systems/{system_id}/sw-baseline")
async def add_software_baseline(
    system_id: int, payload: list[dict[str, Any]] | dict[str, Any]
):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    items = payload if isinstance(payload, list) else [payload]
    data: list[dict[str, Any]] = []
    for item in items:
        missing = _missing_required(item)
        if missing:
            data.append(
                {
                    "softwareName": item.get("softwareName"),
                    "success": False,
                    "errors": {f: [f"{f} is required"] for f in missing},
                }
            )
            continue
        software_id = record.next_software_id()
        stored = {**item, "softwareId": software_id, "systemId": system_id}
        record.software[software_id] = stored
        data.append(
            {
                "softwareName": stored["softwareName"],
                "softwareId": software_id,
                "success": True,
            }
        )
    return ok(data)


@router.put("/systems/{system_id}/sw-baseline")
async def update_software_baseline(
    system_id: int, payload: list[dict[str, Any]] | dict[str, Any]
):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    items = payload if isinstance(payload, list) else [payload]
    data: list[dict[str, Any]] = []
    for item in items:
        sid = item.get("softwareId")
        if not sid:
            data.append(
                {
                    "softwareName": item.get("softwareName"),
                    "success": False,
                    "errors": {"softwareId": ["softwareId is required for PUT"]},
                }
            )
            continue
        existing = record.software.get(sid)
        if existing is None:
            data.append(
                {
                    "softwareId": sid,
                    "success": False,
                    "errors": {"softwareId": [f"softwareId {sid} not found"]},
                }
            )
            continue
        existing.update(item)
        data.append(
            {
                "softwareId": sid,
                "softwareName": existing.get("softwareName"),
                "success": True,
            }
        )
    return ok(data)


@router.delete("/systems/{system_id}/sw-baseline")
async def delete_software_baseline(
    system_id: int, payload: list[dict[str, Any]] | dict[str, Any]
):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    items = payload if isinstance(payload, list) else [payload]
    data: list[dict[str, Any]] = []
    for item in items:
        sid = item.get("softwareId")
        if sid and sid in record.software:
            del record.software[sid]
            data.append({"softwareId": sid, "success": True})
        else:
            data.append(
                {
                    "softwareId": sid,
                    "success": False,
                    "errors": {"softwareId": [f"softwareId {sid} not found"]},
                }
            )
    return ok(data)
