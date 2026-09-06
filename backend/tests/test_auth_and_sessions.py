from app.images.presets import PRESET_AXES, PRESETS


def _full_preset_selection():
    return {axis: PRESETS[axis][0][0] for axis in PRESET_AXES}


def test_verify_rejects_wrong_code(client):
    resp = client.post("/api/auth/verify", json={"code": "wrong"})
    assert resp.status_code == 401


def test_verify_accepts_correct_code(client):
    resp = client.post("/api/auth/verify", json={"code": "testcode"})
    assert resp.status_code == 200
    assert resp.json()["token"]


def test_sessions_require_auth(client):
    resp = client.get("/api/sessions")
    assert resp.status_code == 401


def test_create_session_generates_portrait_synchronously(client, auth_headers):
    resp = client.post("/api/sessions", json={"presets": _full_preset_selection()}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["index"] == 1
    assert body["portrait"]["status"] == "done"
    assert body["portrait"]["url"] is not None


def test_create_session_rejects_incomplete_presets(client, auth_headers):
    incomplete = _full_preset_selection()
    del incomplete["glasses"]
    resp = client.post("/api/sessions", json={"presets": incomplete}, headers=auth_headers)
    assert resp.status_code == 422  # pydantic이 필수 필드 누락을 먼저 걸러낸다


def test_sessions_are_isolated_by_code(client):
    resp1 = client.post("/api/auth/verify", json={"code": "testcode"})
    token1 = resp1.json()["token"]
    headers1 = {"Authorization": f"Bearer {token1}"}
    client.post("/api/sessions", json={"presets": _full_preset_selection()}, headers=headers1)

    listing = client.get("/api/sessions", headers=headers1)
    assert listing.status_code == 200
    assert len(listing.json()["sessions"]) == 1


def test_new_session_does_not_overwrite_previous(client, auth_headers):
    client.post("/api/sessions", json={"presets": _full_preset_selection()}, headers=auth_headers)
    client.post("/api/sessions", json={"presets": _full_preset_selection()}, headers=auth_headers)
    listing = client.get("/api/sessions", headers=auth_headers)
    sessions = listing.json()["sessions"]
    assert len(sessions) == 2
    assert {s["index"] for s in sessions} == {1, 2}


def test_portrait_retry_limited_to_two(client, auth_headers):
    create_resp = client.post(
        "/api/sessions", json={"presets": _full_preset_selection()}, headers=auth_headers
    )
    session_id = create_resp.json()["id"]

    r1 = client.post(f"/api/sessions/{session_id}/portrait/retry", headers=auth_headers)
    assert r1.status_code == 200
    assert r1.json()["portrait"]["retry_count"] == 1

    r2 = client.post(f"/api/sessions/{session_id}/portrait/retry", headers=auth_headers)
    assert r2.json()["portrait"]["retry_count"] == 2

    r3 = client.post(f"/api/sessions/{session_id}/portrait/retry", headers=auth_headers)
    assert r3.status_code == 409


def test_start_session_generates_scene_one_and_backgrounds_rest(client, auth_headers):
    create_resp = client.post(
        "/api/sessions", json={"presets": _full_preset_selection()}, headers=auth_headers
    )
    session_id = create_resp.json()["id"]

    start_resp = client.post(f"/api/sessions/{session_id}/start", headers=auth_headers)
    assert start_resp.status_code == 200
    body = start_resp.json()
    assert body["story_time"] == "20:30"
    assert body["scene"]["id"] == 1
    assert body["scene"]["image_url"] is not None
