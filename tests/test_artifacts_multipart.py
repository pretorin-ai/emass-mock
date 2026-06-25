"""POST /api/systems/{id}/artifacts accepts the real multipart upload contract.

The real eMASS artifacts endpoint takes a ``multipart/form-data`` body with a binary
``filename`` part (plus optional isTemplate/type/category). The harness records the
uploaded bytes so integration tests can assert exactly what eMASS received — this is
what lets callers exercise real file-upload paths against the live mock instead of
stubbing the HTTP client. The legacy JSON-descriptor path still works.
"""

from __future__ import annotations

import base64
import json


def test_multipart_upload_records_file_bytes(client, headers):
    body = json.dumps({"hello": "world"}).encode("utf-8")
    resp = client.post(
        "/api/systems/1/artifacts",
        files={"filename": ("checklist.cklb", body, "application/json")},
        data={"type": "STIG Checklist", "category": "Evidence", "isTemplate": "false"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    row = resp.json()["data"][0]
    assert row == {"filename": "checklist.cklb", "success": True, "systemId": 1}

    stored = client.get("/api/systems/1/artifacts", headers=headers).json()["data"]
    assert len(stored) == 1
    art = stored[0]
    assert art["filename"] == "checklist.cklb"
    assert art["type"] == "STIG Checklist"
    assert art["category"] == "Evidence"
    assert art["isTemplate"] is False
    assert art["size"] == len(body)
    # The exact bytes eMASS received round-trip back for assertion.
    assert base64.b64decode(art["content_b64"]) == body


def test_multipart_defaults_type_and_category(client, headers):
    resp = client.post(
        "/api/systems/1/artifacts",
        files={"filename": ("plain.ckl", b"<CHECKLIST/>", "application/xml")},
        headers=headers,
    )
    assert resp.status_code == 200
    art = client.get("/api/systems/1/artifacts", headers=headers).json()["data"][0]
    assert art["type"] == "Other"
    assert art["category"] == "Evidence"
    assert art["isTemplate"] is False


def test_json_descriptor_path_still_supported(client, headers):
    """Backward compatibility: the original JSON-descriptor upload is unchanged."""
    resp = client.post(
        "/api/systems/1/artifacts",
        json=[{"filename": "ssp.pdf", "type": "SSP"}],
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"][0]["filename"] == "ssp.pdf"
    stored = client.get("/api/systems/1/artifacts", headers=headers).json()["data"]
    assert stored[0]["filename"] == "ssp.pdf"


def test_multipart_unknown_system_404(client, headers):
    resp = client.post(
        "/api/systems/999/artifacts",
        files={"filename": ("x.cklb", b"{}", "application/json")},
        headers=headers,
    )
    assert resp.status_code == 404
