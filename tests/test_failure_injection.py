"""Pillar 2: orchestrated failure injection."""


def test_per_control_failure_in_batch(client, headers):
    client.post("/_admin/failures", json={"control_status": {"SC-7": 422}})
    resp = client.put(
        "/api/systems/1/controls",
        json=[{"acronym": "AC-2"}, {"acronym": "SC-7"}],
        headers=headers,
    )
    rows = {r["acronym"]: r for r in resp.json()["data"]}
    assert rows["AC-2"]["success"] is True
    assert rows["SC-7"]["success"] is False
    assert rows["SC-7"]["errors"][0]["code"] == "422"


def test_rejected_control_is_not_stored(client, headers):
    client.post("/_admin/failures", json={"control_status": {"SC-7": 422}})
    client.put(
        "/api/systems/1/controls",
        json=[{"acronym": "AC-2"}, {"acronym": "SC-7"}],
        headers=headers,
    )
    listed = client.get("/api/systems/1/controls", headers=headers).json()["data"]
    assert {c["acronym"] for c in listed} == {"AC-2"}


def test_global_status_override(client, headers):
    client.post("/_admin/failures", json={"global_status": 503})
    resp = client.get("/api/systems", headers=headers)
    assert resp.status_code == 503
    assert resp.json()["meta"]["errorMessage"]


def test_path_status_override_is_scoped(client, headers):
    client.post(
        "/_admin/failures",
        json={"path_status": {"/api/systems/1/controls": 500}},
    )
    assert client.put(
        "/api/systems/1/controls", json=[], headers=headers
    ).status_code == 500
    # Other paths unaffected.
    assert client.get("/api/systems", headers=headers).status_code == 200


def test_admin_reset_clears_state_and_failures(client, headers):
    client.put("/api/systems/1/controls", json=[{"acronym": "AC-2"}], headers=headers)
    client.post("/_admin/failures", json={"global_status": 503})
    client.post("/_admin/reset")
    assert client.get("/api/systems/1/controls", headers=headers).json()["data"] == []
    state = client.get("/_admin/state").json()
    assert state["failures"]["global_status"] is None
