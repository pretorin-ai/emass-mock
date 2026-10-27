"""Test results: assessment-procedure keyed, CCI reported back, spec filters on GET."""

from tests.payloads import result_row


def test_unknown_assessment_procedure_fails_per_row(client, headers, conforms):
    resp = client.post(
        "/api/systems/1/test-results",
        json=[result_row("AC-1.1"), result_row("SV-000054_rule"), result_row("AC-2")],
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    conforms("addTestResultsBySystemId", resp.json())
    rows = resp.json()["data"]
    assert rows[0] == {"systemId": 1, "success": True, "cci": "000001"}
    assert rows[1]["success"] is False
    assert "cci" not in rows[1]
    assert rows[1]["errors"] == [
        "assessmentProcedure: SV-000054_rule is not an assessment procedure on system 1"
    ]
    assert rows[2]["success"] is False
    stored = client.get("/api/systems/1/test-results", headers=headers).json()["data"]
    assert [r["assessmentProcedure"] for r in stored] == ["AC-1.1"]


def test_invalid_compliance_status_fails_per_row(client, headers):
    resp = client.post(
        "/api/systems/1/test-results",
        json=[result_row("AC-1.1", complianceStatus="Pass")],
        headers=headers,
    )
    assert resp.status_code == 200
    row = resp.json()["data"][0]
    assert row["success"] is False
    assert row["errors"][0].startswith("complianceStatus:")


def test_admin_can_seed_assessment_procedures(client, headers):
    client.post("/_admin/systems/1/assessment-procedures", json={"SC-8.1": "002418"})
    resp = client.post("/api/systems/1/test-results", json=[result_row("SC-8.1")], headers=headers)
    assert resp.json()["data"] == [{"systemId": 1, "success": True, "cci": "002418"}]
    table = client.get("/_admin/systems/1/assessment-procedures").json()
    assert table["SC-8.1"] == "002418"
    assert table["AC-1.1"] == "000001"


def test_get_latest_only_defaults_true(client, headers, read_headers):
    client.post(
        "/api/systems/1/test-results",
        json=[
            result_row("AC-1.1", testDate=100, complianceStatus="Non-Compliant"),
            result_row("AC-1.1", testDate=200, complianceStatus="Compliant"),
            result_row("AC-2.1", testDate=150),
        ],
        headers=headers,
    )
    latest = client.get("/api/systems/1/test-results", headers=read_headers).json()["data"]
    by_ap = {r["assessmentProcedure"]: r for r in latest}
    assert set(by_ap) == {"AC-1.1", "AC-2.1"}
    assert by_ap["AC-1.1"]["complianceStatus"] == "Compliant"

    every = client.get("/api/systems/1/test-results?latestOnly=false", headers=read_headers).json()[
        "data"
    ]
    assert len(every) == 3


def test_get_filters(client, headers, read_headers):
    client.post(
        "/api/systems/1/test-results",
        json=[result_row("AC-1.1"), result_row("AC-2.1"), result_row("SC-7.1")],
        headers=headers,
    )

    def procedures(query: str) -> set[str]:
        rows = client.get(f"/api/systems/1/test-results?{query}", headers=read_headers).json()
        return {r["assessmentProcedure"] for r in rows["data"]}

    assert procedures("controlAcronyms=AC-1,SC-7") == {"AC-1.1", "SC-7.1"}
    assert procedures("assessmentProcedures=AC-2.1") == {"AC-2.1"}
    assert procedures("ccis=CCI-000001,001097") == {"AC-1.1", "SC-7.1"}
