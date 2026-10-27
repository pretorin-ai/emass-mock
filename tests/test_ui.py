"""Testing UI: pages render, forms change state, and the request log records traffic."""

import base64
from urllib.parse import quote

import pytest

from emass_mock.failures import get_failures
from emass_mock.traffic import get_traffic
from tests.payloads import control_row, result_row


@pytest.fixture(autouse=True)
def _clean_traffic():
    get_traffic().clear()
    yield
    get_traffic().clear()


@pytest.mark.parametrize(
    "path", ["/ui/", "/ui/console", "/ui/traffic", "/ui/failures", "/ui/systems/1"]
)
def test_pages_render(client, path):
    resp = client.get(path)
    assert resp.status_code == 200, resp.text
    assert "MOCK" in resp.text
    assert "cdn." not in resp.text  # no external assets; the UI works offline


def test_static_assets_are_served(client):
    for name in ("ui.css", "console.js", "traffic.js"):
        assert client.get(f"/ui/static/{name}").status_code == 200


def test_unknown_system_page_is_404(client):
    assert client.get("/ui/systems/999").status_code == 404


def test_system_page_shows_stored_data(client, headers):
    client.put("/api/systems/1/controls", json=[control_row("AC-2")], headers=headers)
    client.post("/api/systems/1/test-results", json=[result_row("AC-1.1")], headers=headers)
    client.post(
        "/api/systems/1/artifacts",
        files={"file": ("policy.pdf", b"%PDF-1.4", "application/pdf")},
        headers=headers,
    )
    page = client.get("/ui/systems/1").text
    assert "AC-2" in page
    assert "AC-1.1" in page
    assert "policy.pdf" in page
    assert "not spec" in page  # the emu-style part name is flagged


def test_dashboard_lists_recent_requests(client, headers):
    client.get("/api/systems", headers=headers)
    page = client.get("/ui/").text
    assert "getSystems" in page


def test_failure_forms(client):
    client.post("/ui/failures/global", data={"global_status": "503", "latency_seconds": "0.5"})
    f = get_failures()
    assert f.global_status == 503
    assert f.latency_seconds == 0.5
    assert f.artifact_force_empty is False

    client.post("/ui/failures/rule", data={"kind": "control", "key": "sc-7", "status": "422"})
    client.post(
        "/ui/failures/rule", data={"kind": "path", "key": "/api/systems/1/poams", "status": "409"}
    )
    client.post(
        "/ui/failures/rule", data={"kind": "artifact_suffix", "key": ".cklb", "status": "415"}
    )
    assert f.control_status == {"SC-7": 422}
    assert f.path_status == {"/api/systems/1/poams": 409}
    assert f.artifact_filename_status == {".cklb": 415}
    page = client.get("/ui/failures").text
    assert "SC-7" in page and "/api/systems/1/poams" in page and ".cklb" in page

    client.post("/ui/failures/rule/delete", data={"kind": "control", "key": "SC-7"})
    assert f.control_status == {}
    client.post("/ui/failures/clear")
    assert f.global_status is None and f.path_status == {}


def test_procedure_forms(client, headers):
    client.post(
        "/ui/systems/1/assessment-procedures", data={"procedure": "SC-8.1", "cci": "CCI-002418"}
    )
    resp = client.post("/api/systems/1/test-results", json=[result_row("SC-8.1")], headers=headers)
    assert resp.json()["data"][0]["cci"] == "002418"
    client.post("/ui/systems/1/assessment-procedures/delete", data={"procedure": "SC-8.1"})
    resp = client.post("/api/systems/1/test-results", json=[result_row("SC-8.1")], headers=headers)
    assert resp.json()["data"][0]["success"] is False


def test_reset_form(client, headers):
    client.put("/api/systems/1/controls", json=[control_row("AC-2")], headers=headers)
    client.post("/ui/reset")
    assert client.get("/api/systems/1/controls", headers=headers).json()["data"] == []


# --------------------------------------------------------------- traffic log


def test_traffic_records_stateful_request(client, headers):
    resp = client.post("/api/systems/1/test-results", json=[result_row("AC-1.1")], headers=headers)
    entry_id = int(resp.headers["x-emass-mock-request-id"])
    entry = client.get(f"/_admin/requests/{entry_id}").json()
    assert entry["method"] == "POST"
    assert entry["path"] == "/api/systems/1/test-results"
    assert entry["operation_id"] == "addTestResultsBySystemId"
    assert entry["handled_by"] == "stateful"
    assert entry["status"] == 200
    assert entry["auth"] == {"api_key": "valid", "user_uid": "test-user"}
    assert entry["request_headers"]["api-key"] == "••••-key"
    assert entry["request_body"][0]["assessmentProcedure"] == "AC-1.1"
    assert entry["response_body"]["data"][0]["cci"] == "000001"
    assert entry["spec_errors"] == []


def test_traffic_flags_spec_violations(client, headers):
    client.post(
        "/api/systems/1/test-results", json=[result_row("AC-1.1", cci="000001")], headers=headers
    )
    summary = client.get("/_admin/requests").json()["entries"][-1]
    assert summary["status"] == 400
    assert summary["spec_errors"] == 1
    entry = client.get(f"/_admin/requests/{summary['id']}").json()
    assert "cci" in entry["spec_errors"][0]


def test_traffic_flags_paths_outside_the_spec(client, headers):
    client.post("/api/systems/1/scan-results", content=b"x", headers=headers)
    entry = client.get("/_admin/requests").json()["entries"][-1]
    assert entry["operation_id"] is None
    assert entry["handled_by"] == "unhandled"
    assert entry["status"] == 501


def test_traffic_records_injected_failures(client, headers):
    client.post("/_admin/failures", json={"global_status": 503})
    client.get("/api/systems", headers=headers)
    entry = client.get("/_admin/requests").json()["entries"][-1]
    assert entry["status"] == 503
    assert entry["handled_by"] == "injected"


def test_traffic_records_auth_problems(client):
    client.get("/api/systems")
    client.get("/api/systems", headers={"api-key": "wrong-key"})
    entries = client.get("/_admin/requests").json()["entries"]
    assert [e["api_key"] for e in entries[-2:]] == ["missing", "wrong"]


def test_traffic_lists_multipart_parts(client, headers):
    client.post(
        "/api/systems/1/artifacts",
        files={"filename": ("checklist.cklb", b"{}", "application/json")},
        data={"type": "STIG Checklist"},
        headers=headers,
    )
    entry_id = client.get("/_admin/requests").json()["entries"][-1]["id"]
    parts = client.get(f"/_admin/requests/{entry_id}").json()["request_parts"]
    by_name = {p["name"]: p for p in parts}
    assert by_name["filename"]["filename"] == "checklist.cklb"
    assert by_name["filename"]["binary"] is True
    assert by_name["type"]["value"] == "STIG Checklist"


def test_traffic_skips_harness_routes(client):
    client.get("/_admin/state")
    client.get("/ui/")
    client.get("/health")
    assert client.get("/_admin/requests").json()["entries"] == []


def test_traffic_after_and_clear(client, headers):
    for _ in range(3):
        client.get("/api", headers=headers)
    entries = client.get("/_admin/requests").json()["entries"]
    first = entries[0]["id"]
    newer = client.get(f"/_admin/requests?after={first}").json()["entries"]
    assert [e["id"] for e in newer] == [e["id"] for e in entries[1:]]
    client.delete("/_admin/requests")
    assert client.get("/_admin/requests").json()["entries"] == []
    assert client.get(f"/_admin/requests/{first}").status_code == 404


# ----------------------------------------------------------- console support


def test_operations_catalog_flags_stateful(client):
    ops = {o["operationId"]: o for o in client.get("/_admin/operations").json()}
    assert len(ops) == 104
    for stateful in (
        "testConnection",
        "updateControlBySystemId",
        "addTestResultsBySystemId",
        "addArtifactsBySystemId",
        "updatePoamBySystemId",
        "deleteMilestone",
        "getSystemSwBaseline",
        "addScanResultsBySystemId",
    ):
        assert ops[stateful]["stateful"] is True, stateful
    for proxied in ("getSystemRoles", "getSystemStatusDetails", "addCloudResourcesBySystemId"):
        assert ops[proxied]["stateful"] is False, proxied
    scan = ops["addScanResultsBySystemId"]
    assert scan["body"] == "multipart"
    assert {p["name"] for p in scan["parameters"]} == {"systemId", "scanType", "isBaseline"}
    assert ops["updateControlBySystemId"]["body"] == "json"


def test_examples_are_valid_for_every_json_operation(client):
    ops = client.get("/_admin/operations").json()
    json_ops = [o["operationId"] for o in ops if o["body"] == "json"]
    assert json_ops
    for op in json_ops:
        for mode in ("required", "full"):
            body = client.get(f"/_admin/operations/{op}/example?mode={mode}").json()["body"]
            result = client.post("/_admin/validate", json={"operationId": op, "body": body}).json()
            assert result["valid"], (op, mode, result["errors"])


def test_required_example_round_trips_through_the_mock(client, headers):
    body = client.get("/_admin/operations/addTestResultsBySystemId/example").json()["body"]
    resp = client.post("/api/systems/1/test-results", json=body, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"][0]["success"] is True


def test_validate_reports_errors(client):
    result = client.post(
        "/_admin/validate",
        json={"operationId": "addTestResultsBySystemId", "body": [{"cci": "1"}]},
    ).json()
    assert result["valid"] is False
    assert any("cci" in e for e in result["errors"])
    assert client.post("/_admin/validate", json={"operationId": "nope"}).status_code == 404


def test_settings_endpoint(client):
    settings = client.get("/_admin/settings").json()
    assert settings["spec_version"].startswith("v3.")
    assert settings["systems"] == [1, 2, 3]
    assert settings["unknown_fields"] == "reject"


def test_artifact_download_returns_uploaded_bytes(client, headers):
    client.post(
        "/api/systems/1/artifacts",
        files={"filename": ("ssp.pdf", b"%PDF-1.7 hello", "application/pdf")},
        headers=headers,
    )
    resp = client.get("/_admin/systems/1/artifacts/0/content")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.7 hello"
    assert 'filename="ssp.pdf"' in resp.headers["content-disposition"]
    stored = client.get("/_admin/systems/1/artifacts").json()[0]
    assert base64.b64decode(stored["_content_b64"]) == resp.content
    assert client.get("/_admin/systems/1/artifacts/5/content").status_code == 404


@pytest.mark.parametrize("filename", ["检查.pdf", "résumé.pdf", "report; final.pdf"])
def test_artifact_download_encodes_filename(client, headers, filename):
    uploaded = client.post(
        "/api/systems/1/artifacts",
        files={"filename": (filename, b"file bytes", "application/pdf")},
        headers=headers,
    )
    assert uploaded.status_code == 200
    response = client.get("/_admin/systems/1/artifacts/0/content")
    assert response.status_code == 200
    assert response.content == b"file bytes"
    assert response.headers["content-disposition"] == (
        "attachment; filename*=utf-8''" + quote(filename, safe="")
    )


@pytest.mark.parametrize(
    ("referer", "expected"),
    [
        ("http://testserver/ui/traffic?filter=all", "/ui/traffic?filter=all"),
        ("/ui/systems/1", "/ui/systems/1"),
        ("https://example.com/ui/", "/ui/"),
        ("//example.com/ui/", "/ui/"),
        ("http://testserver/other?next=/ui/", "/ui/"),
        ("http://[invalid/ui/", "/ui/"),
    ],
)
def test_ui_form_redirect_stays_on_this_ui(client, referer, expected):
    response = client.post("/ui/reset", headers={"referer": referer}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == expected


@pytest.mark.parametrize(
    "data",
    [
        {"global_status": "invalid"},
        {"latency_seconds": "invalid"},
        {"latency_seconds": "inf"},
        {"latency_seconds": "-1"},
    ],
)
def test_invalid_failure_form_returns_validation_error_without_mutating_state(client, data):
    get_failures().global_status = 503
    response = client.post("/ui/failures/global", data=data)
    assert response.status_code == 422
    assert response.json()["detail"]
    assert get_failures().global_status == 503


def test_file_in_numeric_form_field_returns_validation_error(client):
    response = client.post(
        "/ui/failures/rule",
        data={"kind": "path", "key": "/api/systems"},
        files={"status": ("status.txt", b"503", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "status"]
    assert get_failures().path_status == {}


def test_nonfinite_number_in_admin_input_returns_validation_error(client):
    response = client.post(
        "/_admin/failures",
        content=b'{"global_status":NaN}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "global_status"]


def test_empty_failure_form_clears_global_settings(client):
    get_failures().global_status = 503
    response = client.post("/ui/failures/global", data={"global_status": "", "latency_seconds": ""})
    assert response.status_code == 200
    assert get_failures().global_status is None
    assert get_failures().latency_seconds == 0.0
