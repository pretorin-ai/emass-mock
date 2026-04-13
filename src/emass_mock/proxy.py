"""Fallthrough proxy to Stoplight Prism.

For any eMASS path we don't handle statefully, we forward the request to a
Prism instance running the MITRE OpenAPI spec. Prism returns spec-conformant
example responses generated from `x-faker` hints in the spec. This gives
integrators realistic shapes for read-only endpoints (dashboards, workflow
definitions, etc.) without us reimplementing the entire eMASS surface.

If PRISM_URL is unset, unhandled paths return 501 with a clear message.
"""

from __future__ import annotations

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from .config import load_settings

_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-encoding",
    "content-length", "host",
}


async def proxy_to_prism(request: Request) -> Response:
    """Forward an unhandled request to Prism. Caller ensures path is eMASS-spec."""
    settings = load_settings()
    if not settings.prism_url:
        return JSONResponse(
            status_code=501,
            content={
                "meta": {
                    "code": 501,
                    "errorMessage": (
                        f"No stateful handler for {request.method} {request.url.path} and "
                        "PRISM_URL is not configured. Either implement a handler or set "
                        "PRISM_URL to a Stoplight Prism instance serving the eMASS spec."
                    ),
                }
            },
        )

    target = settings.prism_url.rstrip("/") + request.url.path
    if request.url.query:
        target = f"{target}?{request.url.query}"

    headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP}
    body = await request.body()

    async with httpx.AsyncClient(timeout=30.0) as client:
        upstream = await client.request(
            request.method, target, content=body, headers=headers
        )

    passthrough_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in _HOP_BY_HOP
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=passthrough_headers,
        media_type=upstream.headers.get("content-type"),
    )
