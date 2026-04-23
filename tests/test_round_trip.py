"""Pillar 1: deterministic round-tripping — the core value of this harness."""


def test_controls_put_then_get_returns_same_acronyms(client, headers):
    payload = [
        {
            "acronym": "AC-2",
            "responsibleEntities": "System Owner",
            "controlDesignation": "System-Specific",
            "estimatedCompletionDate": 1799644800,
            "implementationNarrative": "AC-2 implementation narrative",
            "implementationStatus": "Planned",
            "slcmCriticality": "Moderate",
            "slcmFrequency": "Quarterly",
            "slcmMethod": "Manual",
            "slcmReporting": "Tracked in Pretorin",
            "slcmTracking": "Tracked in Pretorin",
            "slcmComments": "Tracked in Pretorin",
        },
        {
            "acronym": "SC-7",
            "responsibleEntities": "System Owner",
            "controlDesignation": "System-Specific",
            "estimatedCompletionDate": 1799644800,
            "implementationNarrative": "SC-7 implementation narrative",
            "implementationStatus": "Implemented",
            "slcmCriticality": "Moderate",
            "slcmFrequency": "Quarterly",
            "slcmMethod": "Manual",
            "slcmReporting": "Tracked in Pretorin",
            "slcmTracking": "Tracked in Pretorin",
            "slcmComments": "Tracked in Pretorin",
        },
    ]
    put = client.put("/api/systems/1/controls", json=payload, headers=headers)
    assert put.status_code == 200
    data = put.json()["data"]
    assert [row["acronym"] for row in data] == ["AC-2", "SC-7"]
    assert all(row["success"] for row in data)
    assert all(row["systemId"] == 1 for row in data)

    got = client.get("/api/systems/1/controls", headers=headers).json()["data"]
    assert {c["acronym"] for c in got} == {"AC-2", "SC-7"}


def test_poam_assigns_ids_visible_on_readback(client, headers):
    resp = client.post(
        "/api/systems/1/poams",
        json=[{"description": "Fix SC-7"}, {"description": "Fix AC-2"}],
        headers=headers,
    ).json()["data"]
    assert {r["poamId"] for r in resp} == {1001, 1002}

    listed = client.get("/api/systems/1/poams", headers=headers).json()["data"]
    assert {p["poamId"] for p in listed} == {1001, 1002}


def test_test_results_persist(client, headers):
    client.post(
        "/api/systems/1/test-results",
        json=[
            {
                "cci": "CCI-000054",
                "testedBy": "auditor",
                "testDate": 1799644800,
                "description": "Test result description",
                "complianceStatus": "Compliant",
                "assessmentProcedure": "SV-000054_rule",
            }
        ],
        headers=headers,
    )
    listed = client.get("/api/systems/1/test-results", headers=headers).json()["data"]
    assert len(listed) == 1
    assert listed[0]["cci"] == "CCI-000054"


def test_artifacts_persist(client, headers):
    client.post(
        "/api/systems/1/artifacts",
        json=[{"filename": "ssp.pdf"}],
        headers=headers,
    )
    listed = client.get("/api/systems/1/artifacts", headers=headers).json()["data"]
    assert listed[0]["filename"] == "ssp.pdf"
