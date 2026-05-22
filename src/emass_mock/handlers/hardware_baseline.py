"""Hardware Baseline endpoints.

GET  /api/systems/{systemId}/hw-baseline
POST /api/systems/{systemId}/hw-baseline
PUT  /api/systems/{systemId}/hw-baseline
DELETE /api/systems/{systemId}/hw-baseline

Stateful mirror of the eMASS Hardware Baseline surface. Per-item:
  POST → returns {assetName, hardwareId, success}
  PUT  → requires hardwareId; replaces fields on the matching record
  DELETE → requires hardwareId; idempotent (missing id is success:false but
           reports per-item).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..auth import require_emu_auth
from ..envelope import error, ok
from ..store import get_store

router = APIRouter(
    prefix="/api",
    tags=["hardware-baseline"],
    dependencies=[Depends(require_emu_auth)],
)


@router.get("/systems/{system_id}/hw-baseline")
async def get_hardware_baseline(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return ok(list(record.hardware.values()))


@router.post("/systems/{system_id}/hw-baseline")
async def add_hardware_baseline(
    system_id: int, payload: list[dict[str, Any]] | dict[str, Any]
):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    items = payload if isinstance(payload, list) else [payload]
    data: list[dict[str, Any]] = []
    for item in items:
        if not item.get("assetName"):
            data.append(
                {
                    "assetName": item.get("assetName"),
                    "success": False,
                    "errors": {"assetName": ["assetName is required"]},
                }
            )
            continue
        hardware_id = record.next_hardware_id()
        stored = {**item, "hardwareId": hardware_id, "systemId": system_id}
        record.hardware[hardware_id] = stored
        data.append(
            {
                "assetName": stored["assetName"],
                "hardwareId": hardware_id,
                "success": True,
            }
        )
    return ok(data)


@router.put("/systems/{system_id}/hw-baseline")
async def update_hardware_baseline(
    system_id: int, payload: list[dict[str, Any]] | dict[str, Any]
):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    items = payload if isinstance(payload, list) else [payload]
    data: list[dict[str, Any]] = []
    for item in items:
        hid = item.get("hardwareId")
        if not hid:
            data.append(
                {
                    "assetName": item.get("assetName"),
                    "success": False,
                    "errors": {"hardwareId": ["hardwareId is required for PUT"]},
                }
            )
            continue
        existing = record.hardware.get(hid)
        if existing is None:
            data.append(
                {
                    "hardwareId": hid,
                    "success": False,
                    "errors": {"hardwareId": [f"hardwareId {hid} not found"]},
                }
            )
            continue
        existing.update(item)
        data.append(
            {
                "hardwareId": hid,
                "assetName": existing.get("assetName"),
                "success": True,
            }
        )
    return ok(data)


@router.delete("/systems/{system_id}/hw-baseline")
async def delete_hardware_baseline(
    system_id: int, payload: list[dict[str, Any]] | dict[str, Any]
):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    items = payload if isinstance(payload, list) else [payload]
    data: list[dict[str, Any]] = []
    for item in items:
        hid = item.get("hardwareId")
        if hid and hid in record.hardware:
            del record.hardware[hid]
            data.append({"hardwareId": hid, "success": True})
        else:
            data.append(
                {
                    "hardwareId": hid,
                    "success": False,
                    "errors": {"hardwareId": [f"hardwareId {hid} not found"]},
                }
            )
    return ok(data)
