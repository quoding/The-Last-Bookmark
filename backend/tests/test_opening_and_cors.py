"""오프닝 대사 시딩과 CORS 설정 검증.

Codex의 프론트 통합 대조(worklog_codex, INTEGRATION.md)에서 지적된 두 항목:
1. 시작 대화가 turn=0 메시지로 저장·복원되어야 함
2. 실제 API 서버 CORS 연결 검증 필요
"""

from app.images.presets import PRESET_AXES, PRESETS


def _full_preset_selection():
    return {axis: PRESETS[axis][0][0] for axis in PRESET_AXES}


def test_opening_messages_seeded_on_start_and_restorable(client, auth_headers):
    create_resp = client.post(
        "/api/sessions", json={"presets": _full_preset_selection()}, headers=auth_headers
    )
    session_id = create_resp.json()["id"]
    client.post(f"/api/sessions/{session_id}/start", headers=auth_headers)

    state = client.get(f"/api/sessions/{session_id}", headers=auth_headers).json()
    turn0_messages = [m for m in state["messages"] if m["turn"] == 0]
    assert len(turn0_messages) == 4
    assert turn0_messages[0]["kind"] == "narration"
    assert "사이책방" in turn0_messages[0]["text"]
    assert any(m["kind"] == "reply" for m in turn0_messages)


def test_opening_messages_not_duplicated_on_repeated_start_call(client, auth_headers):
    create_resp = client.post(
        "/api/sessions", json={"presets": _full_preset_selection()}, headers=auth_headers
    )
    session_id = create_resp.json()["id"]
    client.post(f"/api/sessions/{session_id}/start", headers=auth_headers)
    client.post(f"/api/sessions/{session_id}/start", headers=auth_headers)  # 재진입 등으로 재호출되어도

    state = client.get(f"/api/sessions/{session_id}", headers=auth_headers).json()
    turn0_messages = [m for m in state["messages"] if m["turn"] == 0]
    assert len(turn0_messages) == 4


def test_cors_headers_present_for_allowed_origin(client):
    resp = client.options(
        "/api/auth/verify",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
