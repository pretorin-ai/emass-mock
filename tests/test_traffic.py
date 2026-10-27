"""Traffic captures stay bounded and polling follows request completion order."""

import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI

from emass_mock.routers import admin
from emass_mock.traffic import CAPTURE_LIMIT, TrafficLog, TrafficMiddleware, get_traffic


@pytest.fixture(autouse=True)
def isolated_log(monkeypatch):
    monkeypatch.setattr("emass_mock.traffic._log", TrafficLog(500))


@pytest.mark.parametrize("chunk_size", [CAPTURE_LIMIT * 3, 10000])
async def test_capture_limits_do_not_change_delivered_bodies(chunk_size):
    payload = json.dumps({"value": "x" * (CAPTURE_LIMIT * 2)}).encode()

    async def echo(scope, receive, send):
        received = bytearray()
        while True:
            message = await receive()
            received.extend(message.get("body", b""))
            if not message.get("more_body"):
                break
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        for offset in range(0, len(received), chunk_size):
            await send(
                {
                    "type": "http.response.body",
                    "body": bytes(received[offset : offset + chunk_size]),
                    "more_body": offset + chunk_size < len(received),
                }
            )

    async def chunks():
        for offset in range(0, len(payload), chunk_size):
            yield payload[offset : offset + chunk_size]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=TrafficMiddleware(echo)), base_url="http://test"
    ) as client:
        response = await client.put(
            "/api/systems/1/controls",
            content=chunks(),
            headers={"content-type": "application/json"},
        )

    assert response.content == payload
    entry = get_traffic().get(int(response.headers["x-emass-mock-request-id"]))
    assert entry.request_size == entry.response_size == len(payload)
    assert entry.truncated is True
    assert entry.request_body.encode() == entry.response_body.encode() == payload[:CAPTURE_LIMIT]


async def test_polling_includes_slow_requests_that_finish_after_newer_requests():
    app = FastAPI()
    app.add_middleware(TrafficMiddleware)
    app.include_router(admin.router)
    started, release = asyncio.Event(), asyncio.Event()

    @app.get("/api/slow")
    async def slow():
        started.set()
        await release.wait()
        return {"slow": True}

    @app.get("/api/fast")
    async def fast():
        return {"fast": True}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        slow_request = asyncio.create_task(client.get("/api/slow"))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            fast_response = await client.get("/api/fast")
            first_poll = (await client.get("/_admin/requests")).json()
        finally:
            release.set()
            slow_response = await slow_request
        second_poll = (
            await client.get("/_admin/requests", params={"after": first_poll["cursor"]})
        ).json()
        empty_poll = (
            await client.get("/_admin/requests", params={"after": second_poll["cursor"]})
        ).json()

    assert [e["id"] for e in first_poll["entries"]] == [
        int(fast_response.headers["x-emass-mock-request-id"])
    ]
    assert [e["id"] for e in second_poll["entries"]] == [
        int(slow_response.headers["x-emass-mock-request-id"])
    ]
    assert second_poll["cursor"] > first_poll["cursor"]
    assert empty_poll["entries"] == []
    assert empty_poll["cursor"] == second_poll["cursor"]
