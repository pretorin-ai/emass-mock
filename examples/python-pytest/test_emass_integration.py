"""Reference integration tests for an eMASS client.

These are the kinds of assertions you cannot write against Stoplight Prism
alone: round-trip, partial-batch failure, idempotency. Copy this file into
your own project and adapt the client calls to your implementation.

Payloads here are spec-shaped on purpose. The mock validates every write
against MITRE's OpenAPI document, so a row that would be rejected by the
spec is rejected here too (HTTP 400 in the eMASS envelope).
"""

from __future__ import annotations


def control(acronym: str, status: str = "Planned") -> dict:
    """A ``ControlsRequestPutBody`` row with the conditional SLCM fields filled."""
    return {
        "acronym": acronym,
        "responsibleEntities": "System Owner",
        "controlDesignation": "System-Specific",
        "estimatedCompletionDate": 1799644800,
        "implementationNarrative": f"{acronym} implementation narrative",
        "implementationStatus": status,
        "slcmCriticality": "Moderate",
        "slcmFrequency": "Quarterly",
        "slcmMethod": "Manual",
        "slcmReporting": "Tracked in Pretorin",
        "slcmTracking": "Tracked in Pretorin",
        "slcmComments": "Tracked in Pretorin",
    }


# ---------------------------------------------------------------------------
# Pillar 1: deterministic round-tripping
# ---------------------------------------------------------------------------


def test_push_controls_then_fetch_returns_same_data(emass_client):
    """What you PUT is what you GET. Impossible against stateless Prism."""
    put = emass_client.put(
        "/api/systems/1/controls",
        json=[control("AC-2"), control("SC-7", "Implemented")],
    )
    assert put.status_code == 200, put.text
    assert all(row["success"] for row in put.json()["data"])

    got = emass_client.get("/api/systems/1/controls").json()["data"]
    acronyms = {c["acronym"] for c in got}
    assert acronyms == {"AC-2", "SC-7"}


def test_poam_create_assigns_ids_that_persist(emass_client):
    resp = emass_client.post(
        "/api/systems/1/poams",
        json=[
            {
                "status": "Ongoing",
                "vulnerabilityDescription": "SC-7 boundary protection gap",
                "sourceIdentifyingVulnerability": "Assessment",
                "pocOrganization": "Cyberdyne Systems",
                "resources": "2 FTE",
                "externalUid": "ext-1",
            }
        ],
    ).json()
    poam_id = resp["data"][0]["poamId"]
    assert isinstance(poam_id, int)

    listed = emass_client.get("/api/systems/1/poams").json()["data"]
    assert any(p["poamId"] == poam_id for p in listed)


def test_test_results_are_keyed_by_assessment_procedure(emass_client):
    """eMASS takes an assessment procedure, not a CCI, and reports the CCI back."""
    resp = emass_client.post(
        "/api/systems/1/test-results",
        json=[
            {
                "testedBy": "Smith, Joe",
                "testDate": 1799644800,
                "description": "Reviewed the access control policy",
                "complianceStatus": "Compliant",
                "assessmentProcedure": "AC-1.1",
            }
        ],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"][0] == {"systemId": 1, "success": True, "cci": "000001"}


# ---------------------------------------------------------------------------
# Pillar 2: orchestrated failure injection (per-item in a batch)
# ---------------------------------------------------------------------------


def test_partial_batch_failure_matches_real_emass_shape(emass_client, inject_failure):
    """
    Real eMASS returns one data row per submitted control, some with
    success=false + errors[]. Your sync code needs to handle the mixed result.
    """
    inject_failure(control_status={"SC-7": 422})
    resp = emass_client.put(
        "/api/systems/1/controls",
        json=[control("AC-2"), control("SC-7")],
    )
    assert resp.status_code == 200
    rows = {r["acronym"]: r for r in resp.json()["data"]}
    assert rows["AC-2"]["success"] is True
    assert rows["SC-7"]["success"] is False
    # Spec ``Errors``: an array of "key: value" strings.
    assert rows["SC-7"]["errors"] == ["acronym: injected failure (422) for SC-7"]


def test_spec_violation_is_a_400(emass_client):
    """A row the spec would reject is a 400 for the whole batch, in the eMASS envelope."""
    resp = emass_client.put("/api/systems/1/controls", json=[{"acronym": "AC-2"}])
    assert resp.status_code == 400
    assert resp.json()["meta"]["code"] == 400
    assert "responsibleEntities" in resp.json()["meta"]["errorMessage"]


def test_global_503_exercises_retry_logic(emass_client, inject_failure):
    inject_failure(global_status=503)
    resp = emass_client.put("/api/systems/1/controls", json=[control("AC-2")])
    assert resp.status_code == 503
    assert resp.json()["meta"]["errorMessage"]


def test_latency_exercises_timeout_handling(emass_client, inject_failure):
    inject_failure(latency_seconds=0.5)
    resp = emass_client.get("/api/systems")
    assert resp.status_code == 200
    assert resp.elapsed.total_seconds() >= 0.4


# ---------------------------------------------------------------------------
# Pillar: read-only fallthrough to Prism (for endpoints we don't persist)
# ---------------------------------------------------------------------------


def test_unhandled_endpoint_falls_through_to_prism(emass_client):
    """
    Dashboards and other read-only endpoints aren't stateful in this harness;
    they proxy to Prism for spec-conformant example responses. Your code can
    parse them without us maintaining the full eMASS surface.
    """
    # Hit a dashboard endpoint we don't handle. Prism will synthesize a response.
    resp = emass_client.get("/api/dashboards/system-status-details?systemId=1")
    # Prism returns a valid eMASS envelope even for example responses.
    assert resp.status_code in (200, 400, 422)  # Prism may 422 on missing required params.
    assert "meta" in resp.json()
