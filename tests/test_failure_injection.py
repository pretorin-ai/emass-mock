"""Pillar 2: orchestrated failure injection."""

from tests.payloads import control_row


def test_per_control_failure_in_batch(client, headers, conforms):
    client.post("/_admin/failures", json={"control_status": {"SC-7": 422}})
    resp = client.put(
        "/api/systems/1/controls", json=[control_row("AC-2"), control_row("SC-7")], headers=headers
    )
    conforms("updateControlBySystemId", resp.json())
    rows = {r["acronym"]: r for r in resp.json()["data"]}
    assert rows["AC-2"]["success"] is True
    assert rows["SC-7"]["success"] is False
    # Spec ``Errors`` is an array of "key: value" strings, not objects.
    assert rows["SC-7"]["errors"] == ["acronym: injected failure (422) for SC-7"]


def test_rejected_control_is_not_stored(client, headers):
    client.post("/_admin/failures", json={"control_status": {"SC-7": 422}})
    client.put(
        "/api/systems/1/controls", json=[control_row("AC-2"), control_row("SC-7")], headers=headers
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
    assert client.put("/api/systems/1/controls", json=[], headers=headers).status_code == 500
    # Other paths unaffected.
    assert client.get("/api/systems", headers=headers).status_code == 200


def test_artifact_suffix_rejection_and_forced_empty(client, headers):
    client.post("/_admin/failures", json={"artifact_filename_status": {".cklb": 422}})
    rejected = client.post(
        "/api/systems/1/artifacts",
        files={"filename": ("x.cklb", b"{}", "application/json")},
        headers=headers,
    )
    assert rejected.status_code == 422
    accepted = client.post(
        "/api/systems/1/artifacts",
        files={"filename": ("x.ckl", b"<CHECKLIST/>", "application/xml")},
        headers=headers,
    )
    assert accepted.status_code == 200

    client.post("/_admin/failures", json={"artifact_force_empty": True})
    empty = client.post(
        "/api/systems/1/artifacts",
        files={"filename": ("y.ckl", b"<CHECKLIST/>", "application/xml")},
        headers=headers,
    )
    assert empty.status_code == 200
    assert empty.json()["data"] == []


def test_admin_reset_clears_state_and_failures(client, headers):
    client.put("/api/systems/1/controls", json=[control_row("AC-2")], headers=headers)
    client.post("/_admin/systems/1/assessment-procedures", json={"ZZ-1.1": "009999"})
    client.post("/_admin/failures", json={"global_status": 503})
    client.post("/_admin/reset")
    assert client.get("/api/systems/1/controls", headers=headers).json()["data"] == []
    state = client.get("/_admin/state").json()
    assert state["failures"]["global_status"] is None
    assert "ZZ-1.1" not in client.get("/_admin/systems/1/assessment-procedures").json()
