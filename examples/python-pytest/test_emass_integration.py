"""Reference integration tests for an eMASS client.

These are the kinds of assertions you cannot write against Stoplight Prism
alone: round-trip, partial-batch failure, idempotency. Copy this file into
your own project and adapt the client calls to your implementation.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Pillar 1: deterministic round-tripping
# ---------------------------------------------------------------------------


def test_push_controls_then_fetch_returns_same_data(emass_client):
    """What you PUT is what you GET. Impossible against stateless Prism."""
    payload = [
        {"acronym": "AC-2", "implementationStatus": "Planned"},
        {"acronym": "SC-7", "implementationStatus": "Implemented"},
    ]
    put = emass_client.put("/api/systems/1/controls", json=payload)
    assert put.status_code == 200
    assert all(row["success"] for row in put.json()["data"])

    got = emass_client.get("/api/systems/1/controls").json()["data"]
    acronyms = {c["acronym"] for c in got}
    assert acronyms == {"AC-2", "SC-7"}


def test_poam_create_assigns_ids_that_persist(emass_client):
    resp = emass_client.post(
        "/api/systems/1/poams",
        json=[{"description": "Fix SC-7", "externalUid": "ext-1"}],
    ).json()
    poam_id = resp["data"][0]["poamId"]
    assert isinstance(poam_id, int)

    listed = emass_client.get("/api/systems/1/poams").json()["data"]
    assert any(p["poamId"] == poam_id for p in listed)


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
        json=[
            {"acronym": "AC-2", "implementationStatus": "Planned"},
            {"acronym": "SC-7", "implementationStatus": "Planned"},
        ],
    )
    assert resp.status_code == 200
    rows = {r["acronym"]: r for r in resp.json()["data"]}
    assert rows["AC-2"]["success"] is True
    assert rows["SC-7"]["success"] is False
    assert rows["SC-7"]["errors"][0]["code"] == "422"


def test_global_503_exercises_retry_logic(emass_client, inject_failure):
    inject_failure(global_status=503)
    resp = emass_client.put("/api/systems/1/controls", json=[{"acronym": "AC-2"}])
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
