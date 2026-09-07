"""관리자 비용 모니터링 페이지 검증.

- ADMIN_PASSWORD 없으면 비활성화
- 틀린 비밀번호는 401
- LLM·이미지 호출마다 실제 토큰 사용량이 코드별로 기록·집계된다
"""

import uuid

from app.images.presets import PRESET_AXES, PRESETS


def _full_preset_selection():
    return {axis: PRESETS[axis][0][0] for axis in PRESET_AXES}


def test_admin_disabled_without_password(client):
    resp = client.get("/api/admin/usage", headers={"X-Admin-Password": "anything"})
    assert resp.status_code == 503

    page = client.get("/admin")
    assert page.status_code == 503


def test_admin_rejects_wrong_password(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ADMIN_PASSWORD", "correct-horse")
    get_settings.cache_clear()
    try:
        resp = client.get("/api/admin/usage", headers={"X-Admin-Password": "wrong"})
        assert resp.status_code == 401
    finally:
        get_settings.cache_clear()


def test_admin_page_served_with_correct_password_config(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ADMIN_PASSWORD", "correct-horse")
    get_settings.cache_clear()
    try:
        page = client.get("/admin")
        assert page.status_code == 200
        assert "API 비용 모니터링" in page.text
    finally:
        get_settings.cache_clear()


def test_image_and_llm_usage_is_logged_and_aggregated_per_code(client, auth_headers, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ADMIN_PASSWORD", "correct-horse")
    get_settings.cache_clear()
    try:
        create_resp = client.post(
            "/api/sessions",
            json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
            headers=auth_headers,
        )
        session_id = create_resp.json()["id"]
        client.post(f"/api/sessions/{session_id}/start", headers=auth_headers)  # 장면 1 이미지 생성 -> 사용량 기록

        client.post(
            f"/api/sessions/{session_id}/turns",
            json={"request_id": str(uuid.uuid4()), "text": "안녕하세요"},
            headers=auth_headers,
        )  # LLM 호출 -> 사용량 기록

        resp = client.get("/api/admin/usage", headers={"X-Admin-Password": "correct-horse"})
        assert resp.status_code == 200
        rows = resp.json()["usage"]

        image_rows = [r for r in rows if r["code_id"] == "test" and r["kind"] == "image"]
        llm_rows = [r for r in rows if r["code_id"] == "test" and r["kind"] == "llm"]
        assert len(image_rows) >= 1
        assert len(llm_rows) >= 1
        assert image_rows[0]["call_count"] >= 1
        assert llm_rows[0]["text_tokens"] > 0
    finally:
        get_settings.cache_clear()
