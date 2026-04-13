def test_ui_index_renders(client, headers):
    # Push some data first so the page has something to show.
    client.put("/api/systems/1/controls", json=[{"acronym": "AC-2"}], headers=headers)
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "emass-mock" in resp.text
    assert "MOCK" in resp.text  # banner is present


def test_ui_system_detail_renders(client, headers):
    client.put("/api/systems/1/controls", json=[{"acronym": "AC-2"}], headers=headers)
    resp = client.get("/ui/systems/1")
    assert resp.status_code == 200
    assert "AC-2" in resp.text


def test_ui_failures_form_updates_config(client):
    resp = client.post(
        "/ui/failures",
        data={
            "global_status": "503",
            "control_acronym": "",
            "control_status": "",
            "latency_seconds": "0",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    state = client.get("/_admin/state").json()
    assert state["failures"]["global_status"] == 503


def test_ui_reset_button_clears_state(client, headers):
    client.put("/api/systems/1/controls", json=[{"acronym": "AC-2"}], headers=headers)
    resp = client.post("/ui/reset", follow_redirects=False)
    assert resp.status_code == 303
    data = client.get("/api/systems/1/controls", headers=headers).json()["data"]
    assert data == []
