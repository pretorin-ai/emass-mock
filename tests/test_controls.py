def test_update_controls_accepts_batch(client, headers):
    payload = [
        {"acronym": "AC-2", "implementationStatus": "Implemented"},
        {"acronym": "SC-7", "implementationStatus": "Planned"},
    ]
    resp = client.put("/api/systems/1/controls", json=payload, headers=headers)
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert len(body["accepted"]) == 2
    assert body["rejected"] == []


def test_update_controls_partial_failure(client, headers):
    # Inject a failure only for SC-7.
    client.post(
        "/_admin/failures",
        json={"control_status": {"SC-7": 422}},
    )
    payload = [
        {"acronym": "AC-2", "implementationStatus": "Implemented"},
        {"acronym": "SC-7", "implementationStatus": "Planned"},
    ]
    resp = client.put("/api/systems/1/controls", json=payload, headers=headers)
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert [c["acronym"] for c in body["accepted"]] == ["AC-2"]
    assert [c["acronym"] for c in body["rejected"]] == ["SC-7"]


def test_update_controls_unknown_system(client, headers):
    resp = client.put("/api/systems/999/controls", json=[{"acronym": "AC-2"}], headers=headers)
    assert resp.status_code == 404
