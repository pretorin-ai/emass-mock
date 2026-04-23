from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from emass_mock.failures import get_failures
from emass_mock.main import create_app
from emass_mock.store import get_store


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    with TestClient(app) as c:
        yield c
    get_store().reset((1, 2, 3))
    get_failures().reset()


@pytest.fixture
def headers() -> dict[str, str]:
    # EMU sends both headers on all requests; the mock follows that pattern.
    return {"api-key": "test-api-key", "user-uid": "test-user"}
