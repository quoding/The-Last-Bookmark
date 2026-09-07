"""초대 코드 인증의 IP 기준 속도 제한·임시 차단을 검증한다.

Cloudflare Tunnel 뒤에 있으므로 실제 방문자 IP는 CF-Connecting-IP
헤더에서 읽는다. TestClient의 기본 클라이언트 IP("testclient")와
구분하기 위해 헤더를 명시적으로 지정해 테스트한다.
"""

from app.api import rate_limit


def _verify(client, code="wrongcode", ip="1.2.3.4"):
    return client.post("/api/auth/verify", json={"code": code}, headers={"CF-Connecting-IP": ip})


def test_get_client_ip_prefers_cf_header():
    class _FakeRequest:
        headers = {"CF-Connecting-IP": "9.9.9.9"}
        client = None

    assert rate_limit.get_client_ip(_FakeRequest()) == "9.9.9.9"


def test_different_ips_are_tracked_independently(client):
    for _ in range(rate_limit.RATE_LIMIT_MAX_ATTEMPTS):
        resp = _verify(client, ip="1.1.1.1")
        assert resp.status_code == 401

    # 1.1.1.1은 이제 속도 제한에 걸리지만, 다른 IP는 영향 없어야 한다
    limited = _verify(client, ip="1.1.1.1")
    assert limited.status_code == 429

    other_ip = _verify(client, ip="2.2.2.2")
    assert other_ip.status_code == 401


def test_rate_limit_returns_429_after_too_many_attempts_in_window(client):
    ip = "3.3.3.3"
    for _ in range(rate_limit.RATE_LIMIT_MAX_ATTEMPTS):
        resp = _verify(client, ip=ip)
        assert resp.status_code == 401

    resp = _verify(client, ip=ip)
    assert resp.status_code == 429


def test_successful_login_resets_failure_count(client):
    ip = "4.4.4.4"
    for _ in range(rate_limit.RATE_LIMIT_MAX_ATTEMPTS - 1):
        _verify(client, ip=ip)

    ok = _verify(client, code="testcode", ip=ip)
    assert ok.status_code == 200

    # 성공 뒤에는 실패 카운트가 초기화되어 다시 여러 번 시도할 수 있어야 한다
    resp = _verify(client, ip=ip)
    assert resp.status_code == 401


def test_blocked_after_threshold_failures_returns_403(client, monkeypatch):
    ip = "5.5.5.5"
    fake_time = {"t": 1_000_000.0}
    monkeypatch.setattr(rate_limit.time, "time", lambda: fake_time["t"])

    # 속도 제한 창(60초)에 안 걸리게, 시도마다 시간을 충분히 흘려보낸다
    block_started_at = None
    for _ in range(rate_limit.BLOCK_THRESHOLD):
        block_started_at = fake_time["t"]  # 마지막 반복에서의 값이 곧 차단이 걸리는 기준 시각
        _verify(client, ip=ip)
        fake_time["t"] += rate_limit.RATE_LIMIT_WINDOW_SECONDS + 1

    blocked = _verify(client, ip=ip)
    assert blocked.status_code == 403

    # 차단 시간이 지나기 전에는 계속 403
    fake_time["t"] = block_started_at + rate_limit.BLOCK_DURATION_SECONDS - 1
    still_blocked = _verify(client, ip=ip)
    assert still_blocked.status_code == 403

    # 차단 시간이 지나면 다시 시도 가능(속도 제한과는 별개로 401로 돌아옴)
    fake_time["t"] = block_started_at + rate_limit.BLOCK_DURATION_SECONDS + 1
    unblocked = _verify(client, ip=ip)
    assert unblocked.status_code == 401
