"""코드별 접속 허용 IP와 회차 한도 무제한 코드를 검증한다.

사용자 요청: 개발자 코드(muya98)는 회차 한도를 없애고 특정 IP에서만
쓸 수 있게 하고 싶다. 심사용 코드(tainai)는 지금처럼 제한 없이 둔다.
"""

import uuid

from app.images.presets import PRESET_AXES, PRESETS


def _full_preset_selection():
    return {axis: PRESETS[axis][0][0] for axis in PRESET_AXES}


def test_login_succeeds_from_allowed_ip(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("CODE_IP_ALLOWLIST", "test:9.9.9.9")
    get_settings.cache_clear()
    try:
        resp = client.post(
            "/api/auth/verify",
            json={"code": "testcode"},
            headers={"CF-Connecting-IP": "9.9.9.9"},
        )
        assert resp.status_code == 200
    finally:
        get_settings.cache_clear()


def test_login_rejected_from_disallowed_ip(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("CODE_IP_ALLOWLIST", "test:9.9.9.9")
    get_settings.cache_clear()
    try:
        resp = client.post(
            "/api/auth/verify",
            json={"code": "testcode"},
            headers={"CF-Connecting-IP": "1.2.3.4"},
        )
        assert resp.status_code == 403
    finally:
        get_settings.cache_clear()


def test_code_without_allowlist_entry_is_unrestricted(client, monkeypatch):
    """다른 코드에만 IP 제한이 걸려 있으면, 이 코드는 어디서든 접속 가능해야 한다."""
    from app.config import get_settings

    monkeypatch.setenv("CODE_IP_ALLOWLIST", "someothercode:9.9.9.9")
    get_settings.cache_clear()
    try:
        resp = client.post(
            "/api/auth/verify",
            json={"code": "testcode"},
            headers={"CF-Connecting-IP": "1.2.3.4"},
        )
        assert resp.status_code == 200
    finally:
        get_settings.cache_clear()


def test_token_reuse_from_disallowed_ip_is_rejected_on_later_requests(client, monkeypatch):
    """로그인은 허용 IP에서 했더라도, 발급된 토큰을 다른 IP에서 재사용하면 막혀야 한다."""
    from app.config import get_settings

    monkeypatch.setenv("CODE_IP_ALLOWLIST", "test:9.9.9.9")
    get_settings.cache_clear()
    try:
        login = client.post(
            "/api/auth/verify",
            json={"code": "testcode"},
            headers={"CF-Connecting-IP": "9.9.9.9"},
        )
        token = login.json()["token"]

        ok = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {token}", "CF-Connecting-IP": "9.9.9.9"},
        )
        assert ok.status_code == 200

        stolen = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {token}", "CF-Connecting-IP": "6.6.6.6"},
        )
        assert stolen.status_code == 403
    finally:
        get_settings.cache_clear()


def test_unlimited_budget_code_bypasses_session_cap(client, auth_headers, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("IMAGE_BUDGET_SESSIONS", "1")
    monkeypatch.setenv("IMAGE_BUDGET_UNLIMITED_CODES", "test")
    get_settings.cache_clear()
    try:
        for _ in range(3):
            resp = client.post(
                "/api/sessions",
                json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
                headers=auth_headers,
            )
            assert resp.status_code == 200
    finally:
        get_settings.cache_clear()


def test_budget_cap_still_applies_to_codes_not_in_unlimited_list(client, auth_headers, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("IMAGE_BUDGET_SESSIONS", "1")
    monkeypatch.setenv("IMAGE_BUDGET_UNLIMITED_CODES", "someothercode")
    get_settings.cache_clear()
    try:
        first = client.post(
            "/api/sessions",
            json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
            headers=auth_headers,
        )
        assert first.status_code == 200
        second = client.post(
            "/api/sessions",
            json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
            headers=auth_headers,
        )
        assert second.status_code == 403
    finally:
        get_settings.cache_clear()
