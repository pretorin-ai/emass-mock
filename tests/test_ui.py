"""Inspector UI is a debugging aid, not the product. Smoke tests only."""


def test_ui_renders_and_shows_banner(client):
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "MOCK" in resp.text


def test_ui_system_detail_shows_pushed_controls(client, headers):
    client.put(
        "/api/systems/1/controls",
        json=[
            {
                "acronym": "AC-2",
                "responsibleEntities": ["System Owner"],
                "controlDesignation": "System-Specific",
                "estimatedCompletionDate": "2026-07-22",
                "implementationNarrative": "Access control procedures are implemented.",
            }
        ],
        headers=headers,
    )
    resp = client.get("/ui/systems/1")
    assert resp.status_code == 200
    assert "AC-2" in resp.text
