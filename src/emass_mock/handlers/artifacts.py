"""POST /api/systems/{systemId}/artifacts — stateful handler.

Response shape matches MITRE spec `ArtifactsResponsePutPost` — each data item:
    {"filename": str, "success": bool, "systemId": int, "errors": {...}?}

The real artifacts endpoint accepts a ``multipart/form-data`` upload of a single
binary file (per the MITRE OpenAPI: a required ``filename`` file part plus optional
``isTemplate`` / ``type`` / ``category`` fields). This handler accepts **both**:

* ``multipart/form-data`` — the real upload contract. The binary ``filename`` part
  is read and its bytes are recorded (base64) so integration tests can assert the
  exact file eMASS received (e.g. a generated STIG ``.cklb``/``.ckl``). This lets
  callers exercise real file-upload code paths against the live harness rather than
  stubbing the HTTP client.
* ``application/json`` — a JSON descriptor (list or single object), kept for the
  metadata-only ergonomics the harness shipped with originally.

Both branches mirror the upload into the store and echo the spec response shape.
"""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Depends, Request
from starlette.datastructures import UploadFile

from ..auth import require_emu_auth
from ..envelope import error, ok
from ..failures import get_failures
from ..store import get_store

router = APIRouter(prefix="/api", tags=["artifacts"], dependencies=[Depends(require_emu_auth)])


def _as_bool(value: Any) -> bool:
    """Coerce a multipart form string ('true'/'false') to a bool."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


async def _parse_multipart(request: Request) -> list[dict[str, Any]]:
    """Parse the real eMASS multipart artifact upload into store descriptors.

    The binary file rides in the ``filename`` part (matching the OpenAPI schema and
    the client's ``upload_artifact_file``). We record its bytes (base64) + size so a
    test can read the artifact back and validate the exact content uploaded.
    """
    form = await request.form()
    items: list[dict[str, Any]] = []
    upload = form.get("filename")
    descriptor: dict[str, Any] = {
        "isTemplate": _as_bool(form.get("isTemplate")),
        "type": form.get("type") or "Other",
        "category": form.get("category") or "Evidence",
    }
    if isinstance(upload, UploadFile):
        content = await upload.read()
        descriptor["filename"] = upload.filename
        descriptor["size"] = len(content)
        descriptor["content_b64"] = base64.b64encode(content).decode("ascii")
    else:
        # A plain string in the file field — descriptor-only multipart.
        descriptor["filename"] = upload
    items.append(descriptor)
    return items


@router.post("/systems/{system_id}/artifacts")
async def upload_artifacts(system_id: int, request: Request):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")

    content_type = (request.headers.get("content-type") or "").lower()
    if content_type.startswith("multipart/form-data"):
        items = await _parse_multipart(request)
    else:
        payload = await request.json()
        items = payload if isinstance(payload, list) else [payload]

    failures = get_failures()

    # Per-filename-suffix rejection: lets a test reject one format (e.g. ".cklb")
    # while accepting another (".ckl") on this shared path, to exercise fallbacks.
    if failures.artifact_filename_status:
        for art in items:
            name = (art.get("filename") or "").lower()
            for suffix, status_code in failures.artifact_filename_status.items():
                if name.endswith(suffix.lower()):
                    return error(status_code, f"Injected artifact rejection for {suffix}")

    # Force a 2xx with no per-row confirmation (non-compliant/proxied server).
    if failures.artifact_force_empty:
        return ok([])

    data: list[dict[str, Any]] = []
    for art in items:
        stored = {**art, "systemId": system_id}
        record.artifacts.append(stored)
        data.append(
            {
                "filename": art.get("filename"),
                "success": True,
                "systemId": system_id,
            }
        )
    return ok(data)


@router.get("/systems/{system_id}/artifacts")
async def list_artifacts(system_id: int):
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return ok(record.artifacts)
