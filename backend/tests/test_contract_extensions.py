"""사용자 요청으로 추가된 계약 확장을 검증한다.

- 회차 저장 한도는 코드별로 적용된다 (전체 합산이 아니다)
- GET /sessions/{id}에 portrait_confirmed·presets·scenes가 포함된다
- POST /sessions, POST /portrait/retry도 request_id로 멱등 처리된다
- 코드별로 다른 API 키를 쓸 수 있다
"""

import uuid

from app.images.presets import PRESET_AXES, PRESETS


def _full_preset_selection():
    return {axis: PRESETS[axis][0][0] for axis in PRESET_AXES}


def test_budget_is_per_code_not_global(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("IMAGE_BUDGET_SESSIONS", "1")
    get_settings.cache_clear()
    try:
        token_a = client.post("/api/auth/verify", json={"code": "testcode"}).json()["token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        r1 = client.post(
            "/api/sessions",
            json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
            headers=headers_a,
        )
        assert r1.status_code == 200

        # 같은 코드로 2번째 시도는 한도 초과
        r2 = client.post(
            "/api/sessions",
            json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
            headers=headers_a,
        )
        assert r2.status_code == 403
    finally:
        get_settings.cache_clear()


def test_session_state_exposes_portrait_confirmed_and_presets_before_start(client, auth_headers):
    create_resp = client.post(
        "/api/sessions",
        json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
        headers=auth_headers,
    )
    session_id = create_resp.json()["id"]

    # /start를 아직 호출하지 않은 상태
    state = client.get(f"/api/sessions/{session_id}", headers=auth_headers).json()
    assert state["portrait_confirmed"] is False
    assert state["presets"] == _full_preset_selection()

    client.post(f"/api/sessions/{session_id}/start", headers=auth_headers)

    state_after = client.get(f"/api/sessions/{session_id}", headers=auth_headers).json()
    assert state_after["portrait_confirmed"] is True


def test_session_state_scenes_array_has_four_entries_with_names(client, auth_headers):
    create_resp = client.post(
        "/api/sessions",
        json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
        headers=auth_headers,
    )
    session_id = create_resp.json()["id"]
    client.post(f"/api/sessions/{session_id}/start", headers=auth_headers)

    state = client.get(f"/api/sessions/{session_id}", headers=auth_headers).json()
    assert len(state["scenes"]) == 4
    assert [s["id"] for s in state["scenes"]] == [1, 2, 3, 4]
    assert state["scenes"][0]["name"] == "남겨진 것"
    # 장면 이미지는 회차 생성 시점부터 미리 만들어지므로(목 환경은 동기 실행) 이미 있어야 한다
    assert state["scenes"][0]["image_url"] is not None


def test_create_session_request_id_is_idempotent(client, auth_headers):
    rid = str(uuid.uuid4())
    r1 = client.post(
        "/api/sessions",
        json={"request_id": rid, "presets": _full_preset_selection()},
        headers=auth_headers,
    )
    r2 = client.post(
        "/api/sessions",
        json={"request_id": rid, "presets": _full_preset_selection()},
        headers=auth_headers,
    )
    assert r1.json() == r2.json()

    listing = client.get("/api/sessions", headers=auth_headers).json()["sessions"]
    assert len(listing) == 1  # 같은 request_id 재전송으로 중복 생성되지 않았다


def test_portrait_retry_request_id_is_idempotent(client, auth_headers):
    create_resp = client.post(
        "/api/sessions",
        json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
        headers=auth_headers,
    )
    session_id = create_resp.json()["id"]

    rid = str(uuid.uuid4())
    r1 = client.post(
        f"/api/sessions/{session_id}/portrait/retry", json={"request_id": rid}, headers=auth_headers
    )
    r2 = client.post(
        f"/api/sessions/{session_id}/portrait/retry", json={"request_id": rid}, headers=auth_headers
    )
    assert r1.json() == r2.json()
    assert r1.json()["portrait"]["retry_count"] == 1  # 두 번째 요청이 횟수를 추가로 쓰지 않았다


def test_per_code_api_key_resolves_independently(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("CODE_API_KEYS", "alpha:key-a,beta:key-b")
    monkeypatch.setenv("LLM_API_KEY", "global-fallback-key")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.resolve_api_key("alpha", settings.llm_api_key) == "key-a"
        assert settings.resolve_api_key("beta", settings.llm_api_key) == "key-b"
        assert settings.resolve_api_key("unknown_code", settings.llm_api_key) == "global-fallback-key"
    finally:
        get_settings.cache_clear()


def test_build_image_generator_caches_per_code(monkeypatch):
    from app.api.deps import _generators, build_image_generator
    from app.config import get_settings

    monkeypatch.setenv("CODE_API_KEYS", "codeA:key-a,codeB:key-b")
    get_settings.cache_clear()
    _generators.clear()
    try:
        gen_a1 = build_image_generator("codeA")
        gen_a2 = build_image_generator("codeA")
        gen_b = build_image_generator("codeB")
        assert gen_a1 is gen_a2  # 같은 코드는 캐시된 같은 인스턴스
        assert gen_a1 is not gen_b  # 다른 코드는 다른 인스턴스(다른 키)
    finally:
        get_settings.cache_clear()
        _generators.clear()
