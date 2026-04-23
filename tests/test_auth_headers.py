"""Auth behavior mirrors the working EMU client."""


def test_missing_user_uid_rejected_on_read(client):
    resp = client.get("/api/systems", headers={"api-key": "test-api-key"})
    assert resp.status_code == 401


def test_missing_api_key_rejected(client):
    resp = client.get("/api/systems", headers={"user-uid": "test-user"})
    assert resp.status_code == 401
