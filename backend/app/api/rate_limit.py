"""초대 코드 인증 시도에 대한 IP 기준 속도 제한과 차단.

이 규모(초대받은 소수만 접속)에 Redis 같은 별도 인프라는 과하다.
메모리 딕셔너리로 처리하며, 서버 재시작 시 초기화되는 것은 감수한다.

Cloudflare Tunnel 뒤에 있으므로 TCP 연결의 실제 클라이언트 IP는 항상
Cloudflare 엣지 IP다. 실제 방문자 IP는 Cloudflare가 붙여주는
`CF-Connecting-IP` 헤더에서 읽는다.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_ATTEMPTS = 5

BLOCK_THRESHOLD = 30
BLOCK_DURATION_SECONDS = 60 * 30  # 30분

_recent_attempts: dict[str, list[float]] = defaultdict(list)
_failure_counts: dict[str, int] = defaultdict(int)
_blocked_until: dict[str, float] = {}


def get_client_ip(request: Request) -> str:
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    return request.client.host if request.client else "unknown"


def check_rate_limit(ip: str) -> None:
    """차단·속도 제한에 걸리면 예외를 던진다. 통과하면 아무 일도 안 한다."""
    now = time.time()

    blocked_until = _blocked_until.get(ip)
    if blocked_until is not None:
        if now < blocked_until:
            raise HTTPException(
                status_code=403,
                detail="너무 많이 틀려서 접속이 임시로 제한됐어요. 나중에 다시 시도해주세요.",
            )
        # 차단 기간이 지났다. 초기화하고 계속 진행한다.
        _blocked_until.pop(ip, None)
        _failure_counts[ip] = 0

    attempts = _recent_attempts[ip]
    attempts[:] = [t for t in attempts if now - t < RATE_LIMIT_WINDOW_SECONDS]
    if len(attempts) >= RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="시도가 너무 잦아요. 잠시 후 다시 시도해주세요.")


def record_attempt(ip: str, success: bool) -> None:
    """인증 성공/실패 결과를 기록한다. check_rate_limit 통과 뒤에 호출한다."""
    now = time.time()
    if success:
        _recent_attempts.pop(ip, None)
        _failure_counts[ip] = 0
        _blocked_until.pop(ip, None)
        return

    _recent_attempts[ip].append(now)
    _failure_counts[ip] += 1
    if _failure_counts[ip] >= BLOCK_THRESHOLD:
        _blocked_until[ip] = now + BLOCK_DURATION_SECONDS


def reset_all() -> None:
    """테스트 전용: 전역 상태를 비운다."""
    _recent_attempts.clear()
    _failure_counts.clear()
    _blocked_until.clear()
