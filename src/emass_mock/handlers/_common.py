"""Helpers shared by the stateful handlers."""

from __future__ import annotations

from typing import Any

from fastapi import Body
from fastapi.responses import JSONResponse

from ..envelope import error
from ..spec import spec_version, validate_request
from ..store import SystemRecord, get_store

# A raw JSON body of any shape; the spec validator decides what is acceptable.
JSON_BODY = Body(...)


def system_or_404(system_id: int) -> SystemRecord | JSONResponse:
    record = get_store().get_system(system_id)
    if record is None:
        return error(404, f"System {system_id} not found")
    return record


def reject_invalid_body(operation_id: str, payload: Any) -> JSONResponse | None:
    """400 in the eMASS envelope when the body does not match the spec operation.

    eMASS answers a malformed request with a 400 for the whole batch; business
    rules (unknown ids, conditional fields) fail per row inside a 200 instead.
    """
    messages = validate_request(operation_id, payload)
    if not messages:
        return None
    return error(
        400,
        f"Request body does not match {operation_id} in eMASS API {spec_version()}: "
        + "; ".join(messages),
    )


def csv_param(value: str | None) -> set[str]:
    """Comma-separated filter values the way the spec's query params carry them."""
    if not value:
        return set()
    return {part.strip().upper() for part in value.split(",") if part.strip()}


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}
