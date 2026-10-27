"""POST and GET /api/systems/{systemId}/artifacts.

POST (``addArtifactsBySystemId``) is ``multipart/form-data`` only, as in the
spec: a required binary part plus optional ``isTemplate`` / ``type`` /
``category`` text fields and an ``isBulk`` query parameter (``true`` means
the single file is a ``.zip`` of artifacts). A JSON body is a 400; the real
endpoint does not take one.

The spec names the binary part ``filename``. ``deathlabs/emu``, validated
against the live DoD instance, sends it as ``file``. Until that is settled
against a real instance the mock accepts both and records which one arrived
(``_part_name`` in the admin view) so a caller can see what it sent.

The uploaded bytes are kept so an integration test can read back exactly what
eMASS received (``GET /_admin/systems/{id}/artifacts``). The public GET
(``getSystemArtifacts``) returns spec-shaped rows only.
"""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from ..auth import require_emu_auth
from ..envelope import error, ok
from ..failures import get_failures
from ._common import as_bool, system_or_404

OPERATION_POST = "addArtifactsBySystemId"
OPERATION_GET = "getSystemArtifacts"

# Spec part name first, the emu-observed name second.
FILE_PART_NAMES = ("filename", "file")

router = APIRouter(prefix="/api", tags=["artifacts"], dependencies=[Depends(require_emu_auth)])


def public_row(stored: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in stored.items() if not key.startswith("_")}


Upload = tuple[str, UploadFile, bytes, dict[str, Any]]


async def read_upload(request: Request) -> Upload | JSONResponse:
    """Parse a multipart upload; returns (part_name, upload, content, text_fields) or a 400."""
    content_type = (request.headers.get("content-type") or "").lower()
    if not content_type.startswith("multipart/form-data"):
        return error(
            400,
            "This endpoint takes multipart/form-data with a binary part named "
            f"{FILE_PART_NAMES[0]!r}; got {content_type or 'no content-type'}",
        )
    form = await request.form()
    part_name = next((n for n in FILE_PART_NAMES if isinstance(form.get(n), UploadFile)), None)
    if part_name is None:
        return error(400, f"multipart body is missing the binary part {FILE_PART_NAMES[0]!r}")
    upload = form[part_name]
    assert isinstance(upload, UploadFile)
    content = await upload.read()
    fields = {k: v for k, v in form.items() if k != part_name and not isinstance(v, UploadFile)}
    return part_name, upload, content, fields


@router.post("/systems/{system_id}/artifacts")
async def upload_artifacts(system_id: int, request: Request, isBulk: bool = Query(default=False)):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record

    parsed = await read_upload(request)
    if isinstance(parsed, JSONResponse):
        return parsed
    part_name, upload, content, fields = parsed
    name = upload.filename or ""
    if isBulk and not name.lower().endswith(".zip"):
        return error(400, "isBulk=true requires a single file with the .zip extension")

    failures = get_failures()
    lowered = name.lower()
    for suffix, status_code in failures.artifact_filename_status.items():
        if lowered.endswith(suffix.lower()):
            return error(status_code, f"Injected artifact rejection for {suffix}")
    if failures.artifact_force_empty:
        return ok([])

    record.artifacts.append(
        {
            "systemId": system_id,
            "filename": name,
            "isTemplate": as_bool(fields.get("isTemplate", False)),
            "type": fields.get("type") or "Other",
            "category": fields.get("category") or "Evidence",
            "name": name,
            "isInherited": False,
            "fileSize": str(len(content)),
            "mimeContentType": upload.content_type,
            "_part_name": part_name,
            "_is_bulk": isBulk,
            "_content_b64": base64.b64encode(content).decode("ascii"),
        }
    )
    return ok([{"filename": name, "success": True, "systemId": system_id}])


@router.get("/systems/{system_id}/artifacts")
async def list_artifacts(system_id: int, filename: str | None = Query(default=None)):
    record = system_or_404(system_id)
    if isinstance(record, JSONResponse):
        return record
    rows = [
        public_row(art)
        for art in record.artifacts
        if filename is None or art["filename"] == filename
    ]
    return ok(rows)
