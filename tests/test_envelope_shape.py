"""Lock in spec-conformant envelope shapes.

- success `meta` is ONLY {code: 200}, no other keys
- error `meta` is {code, errorMessage}, no `data`
- every error the app raises itself uses that shape, never FastAPI's {detail}
"""


def test_success_meta_shape(client, read_headers, conforms):
    body = client.get("/api/systems", headers=read_headers).json()
    assert body["meta"] == {"code": 200}
    assert "data" in body
    conforms("getSystems", body)


def test_error_meta_shape_on_unknown_system(client, read_headers):
    body = client.get("/api/systems/9999", headers=read_headers).json()
    assert body["meta"]["code"] == 404
    assert "errorMessage" in body["meta"]
    assert "data" not in body


def test_auth_error_shape(client):
    body = client.get("/api/systems").json()
    assert set(body) == {"meta"}
    assert set(body["meta"]) == {"code", "errorMessage"}
    assert body["meta"]["code"] == 401


def test_malformed_json_is_400_in_envelope(client, headers):
    resp = client.put(
        "/api/systems/1/controls",
        content=b"{not json",
        headers={**headers, "content-type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["meta"]["code"] == 400
    assert "detail" not in resp.json()


def test_test_connection_probe(client, read_headers, conforms):
    resp = client.get("/api", headers=read_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == {"success": True}
    conforms("testConnection", resp.json())


def test_harness_routes_keep_fastapi_errors(client):
    body = client.get("/_admin/systems/9999/artifacts").json()
    assert body == {"detail": "System 9999 not found"}
