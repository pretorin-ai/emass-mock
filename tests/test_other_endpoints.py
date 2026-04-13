def test_submit_test_results(client, headers):
    resp = client.post(
        "/api/systems/1/test-results",
        json=[{"cci": "CCI-000054", "testedBy": "auditor"}],
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


def test_upload_artifact(client, headers):
    resp = client.post(
        "/api/systems/1/artifacts",
        json={"filename": "ssp.pdf", "type": "SSP"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"][0]["filename"] == "ssp.pdf"


def test_create_poams_assigns_ids(client, headers):
    resp = client.post(
        "/api/systems/1/poams",
        json=[{"description": "Fix SC-7"}, {"description": "Fix AC-2"}],
        headers=headers,
    )
    data = resp.json()["data"]
    assert len(data) == 2
    assert all("poamId" in d for d in data)
