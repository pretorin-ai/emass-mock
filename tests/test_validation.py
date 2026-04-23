"""Spec-driven validation on intercepted stateful endpoints."""


def test_controls_reject_missing_required_fields(client, headers):
    resp = client.put(
        "/api/systems/1/controls",
        json=[{"acronym": "AC-2"}],
        headers=headers,
    )
    assert resp.status_code == 400
    assert "missing required fields" in resp.json()["meta"]["errorMessage"]


def test_test_results_reject_missing_required_fields(client, headers):
    resp = client.post(
        "/api/systems/1/test-results",
        json=[{"cci": "CCI-000054", "testedBy": "auditor"}],
        headers=headers,
    )
    assert resp.status_code == 400
    assert "missing required fields" in resp.json()["meta"]["errorMessage"]
