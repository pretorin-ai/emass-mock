"""POST /api/systems/{systemId}/device-scan-results (``addScanResultsBySystemId``).

The spec's multipart scan upload: a required ``scanType`` query parameter
(enum taken from the spec), an optional ``isBaseline`` flag, and one binary
part. eMASS parses the scan server-side; the mock records the upload
(filename, scan type, size, which part name carried it) and answers with a
``DeviceScanResultsResponsePost`` row. ``assetsImported`` is 0 because
nothing is parsed.

Uploads are visible at ``GET /_admin/systems/{id}/device-scans``. There is no
public GET for this surface in v3.22.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from ..auth import require_emu_auth
from ..envelope import error, ok
from ..spec import query_enum
from ._common import system_or_404
from .artifacts import read_upload

OPERATION_POST = "addScanResultsBySystemId"

router = APIRouter(
    prefix="/api", tags=["device-scan-results"], dependencies=[Depends(require_emu_auth)]
)


@router.post("/systems/{system_id}/device-scan-results")
async def upload_device_scan(
    system_id: int,
    request: Request,
    scanType: str | None = Query(default=None),
    isBaseline: bool = Query(default=False),
):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record

    allowed = query_enum(OPERATION_POST, "scanType") or []
    if scanType is None:
        return error(400, "scanType query parameter is required: " + ", ".join(allowed))
    if scanType not in allowed:
        return error(400, f"scanType {scanType!r} is not one of " + ", ".join(allowed))

    parsed = await read_upload(request)
    if isinstance(parsed, JSONResponse):
        return parsed
    part_name, upload, content, _fields = parsed
    name = upload.filename or ""

    record.device_scans.append(
        {
            "systemId": system_id,
            "filename": name,
            "scanType": scanType,
            "isBaseline": isBaseline,
            "size": len(content),
            "mimeContentType": upload.content_type,
            "_part_name": part_name,
        }
    )
    return ok([{"filename": name, "assetsImported": 0, "success": True, "systemId": system_id}])
