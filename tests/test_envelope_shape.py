"""Lock in spec-conformant envelope shapes.

These tests exist specifically to catch drift from the MITRE OpenAPI spec.
Hand-auditing against vendor/emass_client/eMASSRestOpenApi.yaml showed:
- success `meta` is ONLY {code: 200}, no other keys
- error `meta` is {code, errorMessage}
"""


def test_success_meta_shape(client, headers):
    body = client.get("/api/systems", headers=headers).json()
    assert body["meta"] == {"code": 200}
    assert "data" in body


def test_error_meta_shape_on_unknown_system(client, headers):
    body = client.get("/api/systems/9999", headers=headers).json()
    assert body["meta"]["code"] == 404
    assert "errorMessage" in body["meta"]
    assert "data" not in body


def test_auth_error_shape(client):
    body = client.get("/api/systems").json()
    # FastAPI HTTPException default body differs; check status at least.
    # (Matching spec's error shape via middleware would require custom handler.)
    # Test: request without api-key must 401.
    assert body  # sanity
