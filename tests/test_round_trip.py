"""Pillar 1: deterministic round-tripping, the core value of this harness."""

from tests.payloads import control_row, poam_row, result_row


def test_controls_put_then_get_returns_same_acronyms(client, headers, read_headers, conforms):
    put = client.put(
        "/api/systems/1/controls", json=[control_row("AC-2"), control_row("SC-7")], headers=headers
    )
    assert put.status_code == 200, put.text
    conforms("updateControlBySystemId", put.json())
    data = put.json()["data"]
    assert [row["acronym"] for row in data] == ["AC-2", "SC-7"]
    assert all(row["success"] for row in data)
    assert all(row["systemId"] == 1 for row in data)
    assert all("errors" not in row for row in data)

    got = client.get("/api/systems/1/controls", headers=read_headers)
    conforms("getSystemControls", got.json())
    rows = {c["acronym"]: c for c in got.json()["data"]}
    assert set(rows) == {"AC-2", "SC-7"}
    assert rows["AC-2"]["implementationNarrative"] == "AC-2 implementation narrative"
    # Read-only ccis comes from the seeded assessment-procedure table.
    assert rows["AC-2"]["ccis"] == "000015,000016"
    assert rows["SC-7"]["ccis"] == "001097"


def test_controls_get_filters_by_acronyms(client, headers, read_headers):
    client.put(
        "/api/systems/1/controls", json=[control_row("AC-2"), control_row("SC-7")], headers=headers
    )
    got = client.get("/api/systems/1/controls?acronyms=sc-7", headers=read_headers).json()
    assert [c["acronym"] for c in got["data"]] == ["SC-7"]


def test_controls_conditional_rules_fail_per_row(client, headers, conforms):
    resp = client.put(
        "/api/systems/1/controls",
        json=[
            control_row("AC-2"),
            control_row("SC-7", implementationStatus="Not Applicable"),
            control_row("IA-2", implementationStatus="Manually Inherited", slcmComments=None),
        ],
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    conforms("updateControlBySystemId", resp.json())
    rows = {r["acronym"]: r for r in resp.json()["data"]}
    assert rows["AC-2"]["success"] is True
    assert rows["SC-7"]["success"] is False
    assert rows["SC-7"]["errors"] == [
        "naJustification: required when implementationStatus is Not Applicable"
    ]
    assert rows["IA-2"]["success"] is False
    assert any(e.startswith("commonControlProvider:") for e in rows["IA-2"]["errors"])
    assert any(e.startswith("slcmComments:") for e in rows["IA-2"]["errors"])
    stored = client.get("/api/systems/1/controls", headers=headers).json()["data"]
    assert {c["acronym"] for c in stored} == {"AC-2"}


def test_poam_assigns_ids_visible_on_readback(client, headers, read_headers, conforms):
    resp = client.post(
        "/api/systems/1/poams",
        json=[poam_row(externalUid="ext-1"), poam_row(vulnerabilityDescription="Fix AC-2")],
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    conforms("addPoamBySystemId", resp.json())
    rows = resp.json()["data"]
    assert [r["poamId"] for r in rows] == [1001, 1002]
    assert rows[0]["externalUid"] == "ext-1"
    assert "externalUid" not in rows[1]
    assert all(r["success"] for r in rows)

    listed = client.get("/api/systems/1/poams", headers=read_headers)
    conforms("getSystemPoams", listed.json())
    assert {p["poamId"] for p in listed.json()["data"]} == {1001, 1002}
    assert {p["displayPoamId"] for p in listed.json()["data"]} == {100001001, 100001002}


def test_test_results_persist_keyed_by_procedure(client, headers, read_headers, conforms):
    resp = client.post("/api/systems/1/test-results", json=[result_row("AC-1.1")], headers=headers)
    assert resp.status_code == 200, resp.text
    conforms("addTestResultsBySystemId", resp.json())
    assert resp.json()["data"] == [{"systemId": 1, "success": True, "cci": "000001"}]

    listed = client.get("/api/systems/1/test-results", headers=read_headers)
    conforms("getSystemTestResults", listed.json())
    row = listed.json()["data"][0]
    assert row["assessmentProcedure"] == "AC-1.1"
    assert row["cci"] == "000001"
    assert row["control"] == "AC-1"
    assert row["complianceStatus"] == "Compliant"


def test_artifacts_persist(client, headers, read_headers, conforms):
    resp = client.post(
        "/api/systems/1/artifacts",
        files={"filename": ("ssp.pdf", b"%PDF-1.4", "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    conforms("addArtifactsBySystemId", resp.json())
    listed = client.get("/api/systems/1/artifacts", headers=read_headers)
    conforms("getSystemArtifacts", listed.json())
    assert listed.json()["data"][0]["filename"] == "ssp.pdf"
