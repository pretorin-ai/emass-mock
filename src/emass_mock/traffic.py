"""Request log for the eMASS surface.

Every request under ``/api`` is recorded with what arrived and what the mock
answered: method, path, the spec operation it maps to, which layer handled
it, the auth headers (redacted), the body (JSON pretty, multipart part list),
the response, and any spec violations in the request body. The testing UI
reads it through ``/_admin/requests`` so a developer can point a real client
at the mock and watch what it sends.

This is a pure ASGI middleware, not ``BaseHTTPMiddleware``, so it can see the
request body without consuming it and see the response body without
buffering the whole thing in front of the client.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import load_settings
from .spec import match_operation, validate_request

CAPTURE_LIMIT = 64 * 1024
RESPONSE_HEADER = "x-emass-mock-request-id"

_PART_HEADER = re.compile(
    rb'Content-Disposition:\s*form-data;\s*name="(?P<name>[^"]*)"(?:;\s*filename="(?P<filename>[^"]*)")?'
    rb"(?P<rest>(?:\r\n[^\r\n]+)*)\r\n\r\n",
    re.IGNORECASE,
)
_PART_CONTENT_TYPE = re.compile(rb"Content-Type:\s*([^\r\n]+)", re.IGNORECASE)


@dataclass
class Entry:
    id: int
    timestamp: str
    method: str
    path: str
    query: str
    operation_id: str | None
    handled_by: str
    cursor: int = 0
    status: int = 0
    duration_ms: float = 0.0
    auth: dict[str, Any] = field(default_factory=dict)
    request_headers: dict[str, str] = field(default_factory=dict)
    request_content_type: str = ""
    request_size: int = 0
    request_body: Any = None
    request_parts: list[dict[str, Any]] = field(default_factory=list)
    spec_errors: list[str] = field(default_factory=list)
    response_content_type: str = ""
    response_size: int = 0
    response_body: Any = None
    truncated: bool = False

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "method": self.method,
            "path": self.path,
            "query": self.query,
            "operation_id": self.operation_id,
            "handled_by": self.handled_by,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "spec_errors": len(self.spec_errors),
            "user_uid": self.auth.get("user_uid"),
            "api_key": self.auth.get("api_key"),
        }


class TrafficLog:
    def __init__(self, limit: int) -> None:
        self._entries: deque[Entry] = deque(maxlen=limit)
        self._next_id = 1
        self._next_cursor = 1

    @property
    def limit(self) -> int:
        return self._entries.maxlen or 0

    def next_id(self) -> int:
        value = self._next_id
        self._next_id += 1
        return value

    def add(self, entry: Entry) -> None:
        # Request ids are reserved at arrival. Poll by completion order so a
        # slow request cannot be skipped after a newer request finishes first.
        entry.cursor = self._next_cursor
        self._next_cursor += 1
        self._entries.append(entry)

    def list(self, after: int = 0, limit: int = 100) -> list[Entry]:
        newer = [e for e in self._entries if e.cursor > after]
        return newer[-limit:]

    def get(self, entry_id: int) -> Entry | None:
        return next((e for e in self._entries if e.id == entry_id), None)

    def clear(self) -> None:
        self._entries.clear()


_log = TrafficLog(int(os.getenv("EMASS_MOCK_TRAFFIC_LIMIT", "500")))


def get_traffic() -> TrafficLog:
    return _log


def entry_dict(entry: Entry) -> dict[str, Any]:
    return asdict(entry)


def _mask(value: str) -> str:
    return "••••" + value[-4:] if len(value) > 4 else "••••"


def _headers(scope: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_name, raw_value in scope.get("headers", []):
        name = raw_name.decode("latin-1").lower()
        value = raw_value.decode("latin-1")
        if name in {"cookie", "authorization"}:
            value = "(redacted)"
        elif name == "api-key":
            value = _mask(value)
        out[name] = value
    return out


def _auth_summary(scope: dict[str, Any]) -> dict[str, Any]:
    raw = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    settings = load_settings()
    key = raw.get("api-key")
    if key is None:
        api_key = "missing"
    elif not settings.require_api_key:
        api_key = "not checked"
    else:
        api_key = "valid" if key == settings.api_key else "wrong"
    return {"api_key": api_key, "user_uid": raw.get("user-uid") or None}


def _parse_json(data: bytes) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return data.decode("utf-8", errors="replace")


def _multipart_parts(data: bytes) -> list[dict[str, Any]]:
    parts = []
    for match in _PART_HEADER.finditer(data):
        filename = match.group("filename")
        content_type = _PART_CONTENT_TYPE.search(match.group("rest") or b"")
        part: dict[str, Any] = {"name": match.group("name").decode("utf-8", "replace")}
        if filename is not None:
            part["filename"] = filename.decode("utf-8", "replace")
            part["binary"] = True
        if content_type:
            part["content_type"] = content_type.group(1).decode("latin-1").strip()
        if filename is None:
            start = match.end()
            end = data.find(b"\r\n--", start)
            if end != -1 and end - start <= 512:
                part["value"] = data[start:end].decode("utf-8", "replace")
        parts.append(part)
    return parts


def _handled_by(scope: dict[str, Any]) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    if path is None:
        return "injected"
    if path == "/api/{path:path}":
        return "prism" if load_settings().prism_url else "unhandled"
    return "stateful"


class TrafficMiddleware:
    """Record every ``/api`` request into the traffic log."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        path = scope.get("path", "")
        if scope.get("type") != "http" or not (path == "/api" or path.startswith("/api/")):
            await self.app(scope, receive, send)
            return

        log = get_traffic()
        entry_id = log.next_id()
        started = time.perf_counter()
        request_chunks: list[bytes] = []
        request_size = 0
        response_chunks: list[bytes] = []
        response_size = 0
        status = 0
        response_headers: dict[str, str] = {}

        async def capture_receive() -> dict[str, Any]:
            nonlocal request_size
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                remaining = max(0, CAPTURE_LIMIT - request_size)
                request_size += len(body)
                if remaining:
                    request_chunks.append(body[:remaining])
            return message

        async def capture_send(message: dict[str, Any]) -> None:
            nonlocal status, response_size
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.append((RESPONSE_HEADER.encode(), str(entry_id).encode()))
                message = {**message, "headers": headers}
                response_headers.update(
                    {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in headers}
                )
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                remaining = max(0, CAPTURE_LIMIT - response_size)
                response_size += len(body)
                if remaining:
                    response_chunks.append(body[:remaining])
            await send(message)

        try:
            await self.app(scope, capture_receive, capture_send)
        finally:
            self._record(
                scope,
                entry_id,
                started,
                b"".join(request_chunks),
                request_size,
                b"".join(response_chunks),
                response_size,
                status,
                response_headers,
            )

    def _record(
        self,
        scope: dict[str, Any],
        entry_id: int,
        started: float,
        request_body: bytes,
        request_size: int,
        response_body: bytes,
        response_size: int,
        status: int,
        response_headers: dict[str, str],
    ) -> None:
        method = scope.get("method", "GET")
        path = scope.get("path", "")
        headers = _headers(scope)
        content_type = headers.get("content-type", "")
        operation_id = match_operation(method, path)
        truncated = request_size > len(request_body) or response_size > len(response_body)

        entry = Entry(
            id=entry_id,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            method=method,
            path=path,
            query=scope.get("query_string", b"").decode("latin-1"),
            operation_id=operation_id,
            handled_by=_handled_by(scope),
            status=status,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            auth=_auth_summary(scope),
            request_headers=headers,
            request_content_type=content_type,
            request_size=request_size,
            response_content_type=response_headers.get("content-type", ""),
            response_size=response_size,
            truncated=truncated,
        )

        if request_body:
            if content_type.startswith("multipart/form-data"):
                entry.request_parts = _multipart_parts(request_body)
            elif "json" in content_type or not content_type:
                entry.request_body = _parse_json(request_body)
            else:
                entry.request_body = request_body[:2048].decode("utf-8", "replace")

        if (
            operation_id
            and isinstance(entry.request_body, (list, dict))
            and request_size == len(request_body)
        ):
            entry.spec_errors = validate_request(operation_id, entry.request_body)
        if operation_id is None:
            entry.spec_errors = [f"{method} {path} is not an operation in the eMASS spec"]

        if response_body:
            if "json" in entry.response_content_type:
                entry.response_body = _parse_json(response_body)
            else:
                entry.response_body = response_body[:2048].decode("utf-8", "replace")

        get_traffic().add(entry)
