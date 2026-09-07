"""장면 이미지를 초상화가 나오는 즉시(회차 생성 시점) 미리 만들기 시작하는지 검증한다.

사용자 요청: 대화 화면 진입 전 대기를 줄이기 위해, 장면 1~4를 /start까지
기다리지 않고 초상화 확인 화면에 머무는 동안 미리 만든다. 그때까지 준비가
안 됐으면 image_url이 null로 오고(스켈레톤), 준비돼 있으면 곧바로 온다.
초상화를 다시 그리면 이전 참조로 만든 장면 이미지는 무효이므로 새로 만든다.
"""

import uuid

from app.images.presets import PRESET_AXES, PRESETS


def _full_preset_selection():
    return {axis: PRESETS[axis][0][0] for axis in PRESET_AXES}


def test_scene_images_are_generated_right_after_portrait_before_start(client, auth_headers):
    create_resp = client.post(
        "/api/sessions",
        json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
        headers=auth_headers,
    )
    session_id = create_resp.json()["id"]

    # /start를 아직 호출하지 않았는데도 장면 이미지가 이미 준비돼 있어야 한다.
    state = client.get(f"/api/sessions/{session_id}", headers=auth_headers).json()
    assert all(s["image_url"] is not None for s in state["scenes"])
    assert state["portrait_confirmed"] is False


def test_start_does_not_block_and_scene_state_reflects_precomputed_images(client, auth_headers):
    create_resp = client.post(
        "/api/sessions",
        json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
        headers=auth_headers,
    )
    session_id = create_resp.json()["id"]

    start_resp = client.post(f"/api/sessions/{session_id}/start", headers=auth_headers)
    assert start_resp.status_code == 200
    assert start_resp.json()["scene"]["image_url"] is not None


def test_portrait_retry_resets_stale_scene_images(client, auth_headers):
    create_resp = client.post(
        "/api/sessions",
        json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
        headers=auth_headers,
    )
    session_id = create_resp.json()["id"]

    before = client.get(f"/api/sessions/{session_id}", headers=auth_headers).json()
    old_scene1_url = before["scenes"][0]["image_url"]
    assert old_scene1_url is not None

    retry_resp = client.post(
        f"/api/sessions/{session_id}/portrait/retry",
        json={"request_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert retry_resp.status_code == 200

    after = client.get(f"/api/sessions/{session_id}", headers=auth_headers).json()
    new_scene1_url = after["scenes"][0]["image_url"]
    assert new_scene1_url is not None
    assert new_scene1_url != old_scene1_url  # 새 초상화를 참조한 새 이미지로 교체됐다


def test_portrait_retry_failure_clears_scene_images_too(client, auth_headers, fake_image_generator, monkeypatch):
    create_resp = client.post(
        "/api/sessions",
        json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
        headers=auth_headers,
    )
    session_id = create_resp.json()["id"]

    def _failing_generate(prompt):
        raise RuntimeError("이미지 생성 실패(테스트)")

    monkeypatch.setattr(fake_image_generator, "generate", _failing_generate)
    retry_resp = client.post(
        f"/api/sessions/{session_id}/portrait/retry",
        json={"request_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["portrait"]["status"] == "failed"

    state = client.get(f"/api/sessions/{session_id}", headers=auth_headers).json()
    assert all(s["image_url"] is None for s in state["scenes"])
