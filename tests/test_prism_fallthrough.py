"""The fallthrough proxy: unknown /api/ paths go to Prism if configured.

When PRISM_URL is unset, unhandled paths return 501 with a clear message —
not a 404, because the path may well be valid eMASS; we just don't handle it.
"""


def test_unhandled_api_path_returns_501_without_prism(client, headers):
    # PRISM_URL is unset in unit tests by default.
    resp = client.get("/api/dashboards/system-status-details", headers=headers)
    assert resp.status_code == 501
    assert "PRISM_URL" in resp.json()["meta"]["errorMessage"]


def test_admin_and_health_are_not_proxied(client):
    assert client.get("/health").status_code == 200
    assert client.post("/_admin/reset").status_code == 200
