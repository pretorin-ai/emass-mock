def test_global_status_override(client, headers):
    client.post("/_admin/failures", json={"global_status": 503})
    resp = client.get("/api/systems", headers=headers)
    assert resp.status_code == 503
    assert resp.json()["meta"]["errorCode"] == "INJECTED"


def test_path_status_override(client, headers):
    client.post(
        "/_admin/failures",
        json={"path_status": {"/api/systems/1/controls": 500}},
    )
    resp = client.put("/api/systems/1/controls", json=[], headers=headers)
    assert resp.status_code == 500
    # Other paths unaffected.
    assert client.get("/api/systems", headers=headers).status_code == 200


def test_admin_reset_clears_state(client, headers):
    client.put(
        "/api/systems/1/controls",
        json=[{"acronym": "AC-2"}],
        headers=headers,
    )
    client.post("/_admin/reset")
    resp = client.get("/api/systems/1/controls", headers=headers)
    assert resp.json()["data"] == []


def test_admin_routes_bypass_failure_injection(client):
    client.post("/_admin/failures", json={"global_status": 503})
    # Admin route must still work even with global failure on.
    resp = client.post("/_admin/reset")
    assert resp.status_code == 200
