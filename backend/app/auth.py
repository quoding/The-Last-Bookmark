"""초대 코드 검증과 토큰 발급 (CLAUDE.md 10.1).

평문 코드는 환경변수나 코드에 두지 않는다. INVITE_CODE_HASHES에
"code_id:sha256(code)" 쌍을 콤마로 구분해 저장하고 서버에서 비교한다.
"""

import hashlib
import time

from fastapi import Header, HTTPException, Request
from jose import JWTError, jwt

from app.api.rate_limit import get_client_ip
from app.config import get_settings

JWT_ALGORITHM = "HS256"
TOKEN_TTL_SECONDS = 60 * 60 * 12  # 12시간


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_code_hashes() -> dict[str, str]:
    """"code_id:hash,code_id:hash" 형식을 {code_id: hash} 딕셔너리로 파싱한다."""
    raw = get_settings().invite_code_hashes
    result: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        code_id, _, code_hash = pair.partition(":")
        if code_id and code_hash:
            result[code_id] = code_hash
    return result


def verify_invite_code(code: str) -> str | None:
    """유효하면 code_id를 돌려주고, 아니면 None."""
    code_hashes = _load_code_hashes()
    submitted_hash = _sha256(code)
    for code_id, stored_hash in code_hashes.items():
        if submitted_hash == stored_hash:
            return code_id
    return None


def issue_token(code_id: str) -> str:
    payload = {"code_id": code_id, "iat": int(time.time())}
    return jwt.encode(payload, get_settings().auth_secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> str:
    """토큰에서 code_id를 꺼낸다. 유효하지 않으면 예외."""
    try:
        payload = jwt.decode(token, get_settings().auth_secret, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.") from exc
    issued_at = payload.get("iat", 0)
    if time.time() - issued_at > TOKEN_TTL_SECONDS:
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다.")
    code_id = payload.get("code_id")
    if not code_id:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
    return code_id


def require_code_id(request: Request, authorization: str = Header(default="")) -> str:
    """FastAPI 의존성. `Authorization: Bearer <token>`에서 code_id를 얻는다.

    코드에 IP 제한이 걸려있으면(예: 개발자 코드를 특정 네트워크로만 묶을 때)
    로그인 이후의 모든 요청에서도 매번 다시 검사한다 — 토큰만 훔쳐서 다른
    곳에서 쓰는 것도 막기 위해서다.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
    token = authorization.removeprefix("Bearer ").strip()
    code_id = decode_token(token)

    client_ip = get_client_ip(request)
    if not get_settings().is_ip_allowed(code_id, client_ip):
        raise HTTPException(status_code=403, detail="이 코드는 허용된 위치에서만 사용할 수 있어요.")

    return code_id
