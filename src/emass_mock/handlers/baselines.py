"""Hardware and software baseline endpoints.

GET, POST, PUT and DELETE on ``/api/systems/{systemId}/hw-baseline`` and
``/sw-baseline``. The two surfaces have the same shape, so one factory builds
both routers from a small description.

* Bodies are validated against the spec's ``*RequestPostBody`` /
  ``PutBody`` / ``DeleteBody`` schemas (arrays only).
* Write responses are ``{"systemId", "<idField>", "success", "errors"?}`` rows,
  which is all the spec declares. The response does not echo ``assetName`` or
  ``softwareName``; callers must pair rows with their request by position.
* GET is paginated with ``pageIndex`` / ``pageSize`` (default 20000) and
  carries the spec's ``pagination`` block.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from ..auth import require_emu_auth
from ..envelope import ok, paginated, row_errors
from ..store import SystemRecord
from ._common import JSON_BODY, reject_invalid_body, system_or_404


@dataclass(frozen=True)
class BaselineSurface:
    path: str
    tag: str
    id_field: str
    get_op: str
    post_op: str
    put_op: str
    delete_op: str
    table: str
    next_id: str


HARDWARE = BaselineSurface(
    path="hw-baseline",
    tag="hardware-baseline",
    id_field="hardwareId",
    get_op="getSystemHwBaseline",
    post_op="addHwBaselineAssets",
    put_op="updateHwBaselineAssets",
    delete_op="deleteHwBaselineAssets",
    table="hardware",
    next_id="next_hardware_id",
)

SOFTWARE = BaselineSurface(
    path="sw-baseline",
    tag="software-baseline",
    id_field="softwareId",
    get_op="getSystemSwBaseline",
    post_op="addSwBaselineAssets",
    put_op="updateSwBaselineAssets",
    delete_op="deleteSwBaselineAssets",
    table="software",
    next_id="next_software_id",
)


def _row(system_id: int, id_field: str, asset_id: str | None, *errors: str) -> dict[str, Any]:
    row: dict[str, Any] = {"systemId": system_id}
    if asset_id is not None:
        row[id_field] = asset_id
    if errors:
        row["success"] = False
        row["errors"] = row_errors(*errors)
    else:
        row["success"] = True
    return row


def build_router(surface: BaselineSurface) -> APIRouter:
    router = APIRouter(prefix="/api", tags=[surface.tag], dependencies=[Depends(require_emu_auth)])
    route = f"/systems/{{system_id}}/{surface.path}"

    def table(record: SystemRecord) -> dict[str, dict[str, Any]]:
        return getattr(record, surface.table)

    @router.get(route)
    async def get_baseline(
        system_id: int,
        request: Request,
        pageIndex: int = Query(default=0, ge=0),
        pageSize: int = Query(default=20000, ge=1),
    ):
        record = system_or_404(system_id)
        if isinstance(record, JSONResponse):
            return record
        rows = list(table(record).values())
        start = pageIndex * pageSize
        return paginated(
            rows[start : start + pageSize],
            page_index=pageIndex,
            page_size=pageSize,
            total=len(rows),
            url=str(request.url),
        )

    @router.post(route)
    async def add_assets(system_id: int, payload: Any = JSON_BODY):
        record = system_or_404(system_id)
        if isinstance(record, JSONResponse):
            return record
        rejected = reject_invalid_body(surface.post_op, payload)
        if rejected is not None:
            return rejected
        data = []
        for item in payload:
            asset_id = getattr(record, surface.next_id)()
            table(record)[asset_id] = {**item, surface.id_field: asset_id, "systemId": system_id}
            data.append(_row(system_id, surface.id_field, asset_id))
        return ok(data)

    @router.put(route)
    async def update_assets(system_id: int, payload: Any = JSON_BODY):
        record = system_or_404(system_id)
        if isinstance(record, JSONResponse):
            return record
        rejected = reject_invalid_body(surface.put_op, payload)
        if rejected is not None:
            return rejected
        data = []
        for item in payload:
            asset_id = item[surface.id_field]
            existing = table(record).get(asset_id)
            if existing is None:
                data.append(
                    _row(
                        system_id,
                        surface.id_field,
                        asset_id,
                        f"{surface.id_field}: {asset_id} not found on system {system_id}",
                    )
                )
                continue
            existing.update(item)
            data.append(_row(system_id, surface.id_field, asset_id))
        return ok(data)

    @router.delete(route)
    async def delete_assets(system_id: int, payload: Any = JSON_BODY):
        record = system_or_404(system_id)
        if isinstance(record, JSONResponse):
            return record
        rejected = reject_invalid_body(surface.delete_op, payload)
        if rejected is not None:
            return rejected
        data = []
        for item in payload:
            asset_id = item.get(surface.id_field)
            if asset_id in table(record):
                del table(record)[asset_id]
                data.append(_row(system_id, surface.id_field, asset_id))
            else:
                data.append(
                    _row(
                        system_id,
                        surface.id_field,
                        asset_id,
                        f"{surface.id_field}: {asset_id} not found on system {system_id}",
                    )
                )
        return ok(data)

    return router


hardware_router = build_router(HARDWARE)
software_router = build_router(SOFTWARE)
