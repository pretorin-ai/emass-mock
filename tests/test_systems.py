def test_list_seeded_systems(client, headers):
    resp = client.get("/api/systems", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert {s["systemId"] for s in data} == {1, 2, 3}


def test_get_unknown_system(client, headers):
    resp = client.get("/api/systems/9999", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["meta"]["errorCode"]
