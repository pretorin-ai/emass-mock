def test_missing_api_key_returns_401(client):
    resp = client.get("/api/systems")
    assert resp.status_code == 401


def test_valid_api_key_allows_access(client, headers):
    resp = client.get("/api/systems", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["code"] == 200
    assert isinstance(body["data"], list)


def test_health_does_not_require_api_key(client):
    resp = client.get("/health")
    assert resp.status_code == 200
