"""Hardware and software baselines: spec row shapes, per-row errors, pagination."""

from dataclasses import dataclass
from typing import Any

import pytest


@dataclass(frozen=True)
class Surface:
    path: str
    id_field: str
    asset: dict[str, Any]
    extra: dict[str, Any]
    get_op: str
    post_op: str
    put_op: str
    delete_op: str


HARDWARE = Surface(
    path="hw-baseline",
    id_field="hardwareId",
    asset={"assetName": "web-01"},
    extra={"nickname": "edge"},
    get_op="getSystemHwBaseline",
    post_op="addHwBaselineAssets",
    put_op="updateHwBaselineAssets",
    delete_op="deleteHwBaselineAssets",
)
SOFTWARE = Surface(
    path="sw-baseline",
    id_field="softwareId",
    asset={"softwareVendor": "Canonical", "softwareName": "Ubuntu", "version": "24.04"},
    extra={"softwareType": "OS"},
    get_op="getSystemSwBaseline",
    post_op="addSwBaselineAssets",
    put_op="updateSwBaselineAssets",
    delete_op="deleteSwBaselineAssets",
)


@pytest.mark.parametrize("s", [HARDWARE, SOFTWARE], ids=["hardware", "software"])
def test_baseline_crud(client, headers, read_headers, conforms, s: Surface):
    url = f"/api/systems/1/{s.path}"

    post = client.post(url, json=[s.asset, s.asset], headers=headers)
    assert post.status_code == 200, post.text
    conforms(s.post_op, post.json())
    rows = post.json()["data"]
    assert all(set(r) == {"systemId", s.id_field, "success"} for r in rows)
    ids = [r[s.id_field] for r in rows]
    assert len(set(ids)) == 2

    got = client.get(url, headers=read_headers)
    conforms(s.get_op, got.json())
    assert [r[s.id_field] for r in got.json()["data"]] == ids
    assert got.json()["pagination"]["totalCount"] == 2

    put = client.put(
        url,
        json=[{**s.asset, s.id_field: ids[0], **s.extra}, {**s.asset, s.id_field: "missing"}],
        headers=headers,
    )
    assert put.status_code == 200, put.text
    conforms(s.put_op, put.json())
    assert put.json()["data"][0] == {"systemId": 1, s.id_field: ids[0], "success": True}
    assert put.json()["data"][1]["success"] is False
    assert put.json()["data"][1]["errors"] == [f"{s.id_field}: missing not found on system 1"]
    stored = client.get(url, headers=read_headers).json()["data"][0]
    assert all(stored[k] == v for k, v in s.extra.items())

    delete = client.request("DELETE", url, json=[{s.id_field: ids[1]}], headers=headers)
    assert delete.status_code == 200, delete.text
    conforms(s.delete_op, delete.json())
    assert delete.json()["data"] == [{"systemId": 1, s.id_field: ids[1], "success": True}]
    assert client.get(url, headers=read_headers).json()["pagination"]["totalCount"] == 1


def test_baseline_get_paginates(client, headers, read_headers, conforms):
    client.post(
        "/api/systems/1/hw-baseline",
        json=[{"assetName": f"host-{i:02d}"} for i in range(5)],
        headers=headers,
    )
    page = client.get("/api/systems/1/hw-baseline?pageIndex=1&pageSize=2", headers=read_headers)
    conforms("getSystemHwBaseline", page.json())
    body = page.json()
    assert [r["assetName"] for r in body["data"]] == ["host-02", "host-03"]
    assert body["pagination"]["pageIndex"] == 1
    assert body["pagination"]["pageSize"] == 2
    assert body["pagination"]["totalCount"] == 5
    assert body["pagination"]["totalPages"] == 3
    assert body["pagination"]["prevPageUrl"].endswith("pageIndex=0&pageSize=2")
    assert body["pagination"]["nextPageUrl"].endswith("pageIndex=2&pageSize=2")


def test_baseline_put_requires_id(client, headers):
    row = {"softwareVendor": "v", "softwareName": "n", "version": "1"}
    resp = client.put("/api/systems/1/sw-baseline", json=[row], headers=headers)
    assert resp.status_code == 400
    assert "softwareId" in resp.json()["meta"]["errorMessage"]


def test_baseline_rejects_single_object(client, headers):
    resp = client.post("/api/systems/1/hw-baseline", json={"assetName": "x"}, headers=headers)
    assert resp.status_code == 400
