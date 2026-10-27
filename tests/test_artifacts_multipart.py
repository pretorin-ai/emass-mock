"""POST /api/systems/{id}/artifacts is the spec's multipart upload, nothing else.

The uploaded bytes are kept so an integration test can assert exactly what
eMASS received (``GET /_admin/systems/{id}/artifacts``), while the public GET
stays in the spec's ``ArtifactsResponseGet`` shape.
"""

from __future__ import annotations

import base64
import json

import pytest
from starlette.datastructures import UploadFile

from emass_mock.spec import query_enum


def test_multipart_upload_records_file_bytes(client, headers, read_headers, conforms):
    body = json.dumps({"hello": "world"}).encode("utf-8")
    resp = client.post(
        "/api/systems/1/artifacts",
        files={"filename": ("checklist.cklb", body, "application/json")},
        data={"type": "STIG Checklist", "category": "Evidence", "isTemplate": "false"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    conforms("addArtifactsBySystemId", resp.json())
    assert resp.json()["data"] == [{"filename": "checklist.cklb", "success": True, "systemId": 1}]

    public = client.get("/api/systems/1/artifacts", headers=read_headers).json()
    conforms("getSystemArtifacts", public)
    art = public["data"][0]
    assert art["filename"] == "checklist.cklb"
    assert art["type"] == "STIG Checklist"
    assert art["category"] == "Evidence"
    assert art["isTemplate"] is False
    assert art["fileSize"] == str(len(body))
    assert not any(key.startswith("_") for key in art)

    raw = client.get("/_admin/systems/1/artifacts").json()[0]
    assert base64.b64decode(raw["_content_b64"]) == body
    assert raw["_part_name"] == "filename"


def test_multipart_defaults_type_and_category(client, headers, read_headers):
    resp = client.post(
        "/api/systems/1/artifacts",
        files={"filename": ("plain.ckl", b"<CHECKLIST/>", "application/xml")},
        headers=headers,
    )
    assert resp.status_code == 200
    art = client.get("/api/systems/1/artifacts", headers=read_headers).json()["data"][0]
    assert art["type"] == "Other"
    assert art["category"] == "Evidence"
    assert art["isTemplate"] is False


def test_emu_style_file_part_is_accepted_and_recorded(client, headers):
    resp = client.post(
        "/api/systems/1/artifacts",
        files={"file": ("policy.pdf", b"%PDF-1.4", "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert client.get("/_admin/systems/1/artifacts").json()[0]["_part_name"] == "file"


def test_json_descriptor_is_rejected(client, headers):
    resp = client.post(
        "/api/systems/1/artifacts",
        json=[{"filename": "ssp.pdf", "type": "SSP"}],
        headers=headers,
    )
    assert resp.status_code == 400
    assert "multipart/form-data" in resp.json()["meta"]["errorMessage"]
    assert client.get("/api/systems/1/artifacts", headers=headers).json()["data"] == []


def test_bulk_requires_zip(client, headers):
    resp = client.post(
        "/api/systems/1/artifacts?isBulk=true",
        files={"filename": ("policy.pdf", b"%PDF-1.4", "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 400
    ok = client.post(
        "/api/systems/1/artifacts?isBulk=true",
        files={"filename": ("policies.zip", b"PK\x03\x04", "application/zip")},
        headers=headers,
    )
    assert ok.status_code == 200
    assert client.get("/_admin/systems/1/artifacts").json()[0]["_is_bulk"] is True


def test_get_filters_by_filename(client, headers, read_headers):
    for name in ("a.pdf", "b.pdf"):
        client.post(
            "/api/systems/1/artifacts",
            files={"filename": (name, b"x", "application/pdf")},
            headers=headers,
        )
    rows = client.get("/api/systems/1/artifacts?filename=b.pdf", headers=read_headers).json()
    assert [r["filename"] for r in rows["data"]] == ["b.pdf"]


def test_multipart_unknown_system_404(client, headers):
    resp = client.post(
        "/api/systems/999/artifacts",
        files={"filename": ("x.cklb", b"{}", "application/json")},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.parametrize("resource", ["artifacts", "device-scan-results"])
@pytest.mark.parametrize("part_name", ["filename", "file", "wrong-part"])
def test_upload_closes_all_multipart_files(client, headers, monkeypatch, resource, part_name):
    closed = []
    original_close = UploadFile.close

    async def track_close(upload):
        await original_close(upload)
        closed.append(upload)

    monkeypatch.setattr(UploadFile, "close", track_close)
    params = {}
    if resource == "device-scan-results":
        params["scanType"] = query_enum("addScanResultsBySystemId", "scanType")[0]
    response = client.post(
        f"/api/systems/1/{resource}",
        params=params,
        files={
            part_name: ("scan.xml", b"x" * (1024 * 1024 + 1), "application/xml"),
            "extra-file": ("extra.txt", b"extra", "text/plain"),
        },
        headers=headers,
    )
    assert response.status_code == (400 if part_name == "wrong-part" else 200)
    assert len(closed) == 2
    assert all(upload.file.closed for upload in closed)
