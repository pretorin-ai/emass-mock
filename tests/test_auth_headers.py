"""Header auth: ``api-key`` everywhere, ``user-uid`` on writes, errors in the envelope."""

import os

from fastapi.testclient import TestClient

from emass_mock.main import create_app


def test_get_without_user_uid_is_allowed(client, read_headers):
    assert client.get("/api/systems", headers=read_headers).status_code == 200


def test_write_without_user_uid_is_rejected_in_envelope(client, read_headers):
    resp = client.put("/api/systems/1/controls", json=[], headers=read_headers)
    assert resp.status_code == 401
    body = resp.json()
    assert body["meta"]["code"] == 401
    assert "user-uid" in body["meta"]["errorMessage"]
    assert "data" not in body and "detail" not in body


def test_missing_api_key_rejected_in_envelope(client):
    resp = client.get("/api/systems", headers={"user-uid": "test-user"})
    assert resp.status_code == 401
    assert resp.json() == {
        "meta": {"code": 401, "errorMessage": "Invalid or missing api-key header"}
    }


def test_wrong_api_key_rejected(client):
    resp = client.get("/api/systems", headers={"api-key": "nope"})
    assert resp.status_code == 401


def test_strict_mode_requires_user_uid_on_get(monkeypatch):
    monkeypatch.setenv("EMASS_MOCK_REQUIRE_USER_UID_ON_ALL", "true")
    with TestClient(create_app()) as strict:
        assert strict.get("/api/systems", headers={"api-key": "test-api-key"}).status_code == 401
        ok = strict.get("/api/systems", headers={"api-key": "test-api-key", "user-uid": "u"})
        assert ok.status_code == 200


def test_auth_can_be_disabled(monkeypatch):
    monkeypatch.setenv("EMASS_MOCK_REQUIRE_API_KEY", "false")
    with TestClient(create_app()) as open_client:
        assert open_client.get("/api/systems").status_code == 200
        assert open_client.put("/api/systems/1/controls", json=[]).status_code == 200
    assert os.getenv("EMASS_MOCK_REQUIRE_API_KEY") == "false"
