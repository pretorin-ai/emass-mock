from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from emass_mock.config import load_settings
from emass_mock.failures import get_failures
from emass_mock.main import create_app
from emass_mock.spec import validate_response
from emass_mock.store import get_store


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    with TestClient(app) as c:
        yield c
    settings = load_settings()
    get_store().reset(settings.seed_system_ids, settings.seed_assessment_procedures)
    get_failures().reset()


@pytest.fixture
def headers() -> dict[str, str]:
    """Both auth headers, as a client doing writes sends them."""
    return {"api-key": "test-api-key", "user-uid": "test-user"}


@pytest.fixture
def read_headers() -> dict[str, str]:
    """Only ``api-key``; what the spec and the live API need on GET."""
    return {"api-key": "test-api-key"}


@pytest.fixture
def conforms() -> Callable[[str, Any], None]:
    """Assert a mock response body matches the spec's declared 200 schema."""

    def _check(operation_id: str, body: Any, status: int = 200) -> None:
        problems = validate_response(operation_id, body, status)
        assert not problems, f"{operation_id} response drifts from spec: {problems}"

    return _check
