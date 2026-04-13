"""Reusable pytest fixtures for integration-testing an eMASS client.

Drop these into your own project's `conftest.py` (or import them) to get:
- `emass_base_url`     — URL of the running emass-mock
- `emass_api_key`      — the key your client should send
- `emass_client`       — httpx.Client pre-configured with headers + base URL
- `reset_emass_state`  — autouse fixture that wipes mock state between tests
- `inject_failure`     — helper that configures failure injection for one test

Assumes emass-mock is reachable at $EMASS_MOCK_URL (default http://localhost:18080
to match this example's docker-compose). Start it before pytest:

    docker compose -f examples/python-pytest/docker-compose.yml up -d
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import httpx
import pytest


@pytest.fixture(scope="session")
def emass_base_url() -> str:
    return os.getenv("EMASS_MOCK_URL", "http://localhost:18080")


@pytest.fixture(scope="session")
def emass_api_key() -> str:
    return os.getenv("EMASS_MOCK_API_KEY", "test-api-key")


@pytest.fixture
def emass_client(emass_base_url: str, emass_api_key: str) -> Iterator[httpx.Client]:
    with httpx.Client(
        base_url=emass_base_url,
        headers={"api-key": emass_api_key, "user-uid": "test-user"},
        timeout=10.0,
    ) as client:
        yield client


@pytest.fixture(autouse=True)
def reset_emass_state(emass_base_url: str) -> Iterator[None]:
    """Reset the mock before every test so tests cannot leak state into each other."""
    httpx.post(f"{emass_base_url}/_admin/reset", timeout=5.0).raise_for_status()
    yield


@pytest.fixture
def inject_failure(emass_base_url: str):
    """Factory: call inject_failure(global_status=503) or inject_failure(control_status={'SC-7': 422})."""

    def _apply(**kwargs) -> None:
        httpx.post(
            f"{emass_base_url}/_admin/failures", json=kwargs, timeout=5.0
        ).raise_for_status()

    return _apply
