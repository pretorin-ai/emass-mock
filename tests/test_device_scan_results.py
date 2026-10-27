"""POST /api/systems/{id}/device-scan-results: the spec path, enum-checked scanType."""


def test_upload_scan(client, headers, conforms):
    resp = client.post(
        "/api/systems/1/device-scan-results?scanType=disaStigViewerCklCklb&isBaseline=true",
        files={"filename": ("host.cklb", b'{"title": "x"}', "application/json")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    conforms("addScanResultsBySystemId", resp.json())
    assert resp.json()["data"] == [
        {"filename": "host.cklb", "assetsImported": 0, "success": True, "systemId": 1}
    ]
    scans = client.get("/_admin/systems/1/device-scans").json()
    assert scans[0]["scanType"] == "disaStigViewerCklCklb"
    assert scans[0]["isBaseline"] is True
    assert scans[0]["size"] == len(b'{"title": "x"}')
    assert scans[0]["_part_name"] == "filename"


def test_scan_type_is_required_and_enum_checked(client, headers):
    files = {"filename": ("scan.nessus", b"<NessusClientData_v2/>", "application/xml")}
    missing = client.post("/api/systems/1/device-scan-results", files=files, headers=headers)
    assert missing.status_code == 400
    assert "scanType" in missing.json()["meta"]["errorMessage"]
    bad = client.post(
        "/api/systems/1/device-scan-results?scanType=nessus", files=files, headers=headers
    )
    assert bad.status_code == 400
    assert "acasNessus" in bad.json()["meta"]["errorMessage"]


def test_old_scan_results_path_falls_through(client, headers):
    """``/scan-results`` is not an eMASS path; it reaches the Prism fallthrough (501 here)."""
    resp = client.post(
        "/api/systems/1/scan-results?scanType=acasNessus",
        files={"filename": ("x", b"x", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 501


def test_state_counts_scans(client, headers):
    client.post(
        "/api/systems/1/device-scan-results?scanType=acasNessus",
        files={"file": ("scan.nessus", b"<x/>", "application/xml")},
        headers=headers,
    )
    state = client.get("/_admin/state").json()
    assert state["systems"][0]["device_scans"] == 1
    assert state["spec_version"].startswith("v3.")
