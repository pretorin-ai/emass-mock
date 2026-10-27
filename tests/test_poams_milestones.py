"""POA&M PUT/DELETE/GET-by-id and the milestones sub-resource."""

from tests.payloads import poam_row


def _create(client, headers, **overrides) -> int:
    resp = client.post("/api/systems/1/poams", json=[poam_row(**overrides)], headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"][0]["poamId"]


def test_put_updates_existing_and_reports_unknown(client, headers, read_headers, conforms):
    poam_id = _create(client, headers, externalUid="ext-1")
    resp = client.put(
        "/api/systems/1/poams",
        json=[
            poam_row(
                poamId=poam_id, displayPoamId=100001001, status="Completed", externalUid="ext-1"
            ),
            poam_row(poamId=4242, displayPoamId=1, status="Ongoing"),
        ],
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    conforms("updatePoamBySystemId", resp.json())
    rows = resp.json()["data"]
    assert rows[0] == {"systemId": 1, "poamId": poam_id, "externalUid": "ext-1", "success": True}
    assert rows[1]["success"] is False
    assert rows[1]["errors"] == ["poamId: 4242 not found on system 1"]

    one = client.get(f"/api/systems/1/poams/{poam_id}", headers=read_headers)
    conforms("getSystemPoamsByPoamId", one.json())
    assert one.json()["data"]["status"] == "Completed"
    assert one.json()["data"]["poamId"] == poam_id


def test_delete_poams(client, headers, conforms):
    poam_id = _create(client, headers)
    resp = client.request(
        "DELETE",
        "/api/systems/1/poams",
        json=[{"poamId": poam_id}, {"poamId": 999}],
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    conforms("deletePoam", resp.json())
    rows = resp.json()["data"]
    assert rows[0] == {"systemId": 1, "poamId": poam_id, "success": True}
    assert rows[1]["success"] is False
    assert client.get(f"/api/systems/1/poams/{poam_id}", headers=headers).status_code == 404


def test_get_system_only_defaults_true(client, headers, read_headers):
    """The spec defaults ``systemOnly`` to true, which hides control-level POA&Ms."""
    _create(client, headers)
    _create(client, headers, controlAcronym="SC-7")
    default = client.get("/api/systems/1/poams", headers=read_headers).json()["data"]
    assert len(default) == 1 and "controlAcronym" not in default[0]
    everything = client.get("/api/systems/1/poams?systemOnly=false", headers=read_headers)
    assert len(everything.json()["data"]) == 2
    filtered = client.get(
        "/api/systems/1/poams?systemOnly=false&controlAcronyms=SC-7", headers=read_headers
    )
    assert [p["controlAcronym"] for p in filtered.json()["data"]] == ["SC-7"]


def test_nested_milestones_get_ids(client, headers, read_headers, conforms):
    poam_id = _create(
        client,
        headers,
        milestones=[{"description": "Patch", "scheduledCompletionDate": 1799644800}],
    )
    listed = client.get(f"/api/systems/1/poams/{poam_id}/milestones", headers=read_headers)
    conforms("getSystemMilestonesByPoamId", listed.json())
    milestone = listed.json()["data"][0]
    assert milestone["description"] == "Patch"
    assert milestone["milestoneId"] == 5001
    assert milestone["poamId"] == poam_id


def test_milestone_crud(client, headers, read_headers, conforms):
    poam_id = _create(client, headers)
    base = f"/api/systems/1/poams/{poam_id}/milestones"

    post = client.post(
        base,
        json=[{"description": "Patch", "scheduledCompletionDate": 1799644800}],
        headers=headers,
    )
    assert post.status_code == 200, post.text
    conforms("addMilestoneBySystemIdAndPoamId", post.json())
    milestone_id = post.json()["data"][0]["milestoneId"]
    assert post.json()["data"][0] == {
        "systemId": 1,
        "poamId": poam_id,
        "milestoneId": milestone_id,
        "success": True,
    }

    put = client.put(
        base,
        json=[
            {
                "milestoneId": milestone_id,
                "description": "Patch and verify",
                "scheduledCompletionDate": 1799731200,
            },
            {"milestoneId": 99, "description": "x", "scheduledCompletionDate": 1},
        ],
        headers=headers,
    )
    assert put.status_code == 200, put.text
    conforms("updateMilestoneBySystemIdAndPoamId", put.json())
    assert put.json()["data"][1]["success"] is False

    one = client.get(f"{base}/{milestone_id}", headers=read_headers)
    conforms("getSystemMilestonesByPoamIdAndMilestoneId", one.json())
    assert one.json()["data"]["description"] == "Patch and verify"

    delete = client.request("DELETE", base, json=[{"milestoneId": milestone_id}], headers=headers)
    assert delete.status_code == 200, delete.text
    conforms("deleteMilestone", delete.json())
    assert client.get(base, headers=read_headers).json()["data"] == []


def test_milestones_reject_unknown_fields(client, headers):
    poam_id = _create(client, headers)
    resp = client.post(
        f"/api/systems/1/poams/{poam_id}/milestones",
        json=[{"description": "x", "scheduledCompletionDate": 1, "status": "Ongoing"}],
        headers=headers,
    )
    assert resp.status_code == 400
    assert "status" in resp.json()["meta"]["errorMessage"]


def test_milestones_on_unknown_poam_is_404(client, headers):
    resp = client.get("/api/systems/1/poams/777/milestones", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["meta"]["code"] == 404
