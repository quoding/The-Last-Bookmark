"""request_id 멱등 처리. CLAUDE.md 5.3.

같은 request_id로 재시도해도 턴 소비·상태 변경·장면 전환이 한 번만
일어나야 한다. 응답 실패와 새로고침은 턴을 소비하지 않는다.
"""

import uuid

from sqlalchemy.orm import Session as DbSession

from app.models import RequestLog


def get_cached_response(db: DbSession, request_id: str) -> dict | None:
    log = db.get(RequestLog, request_id)
    return log.response_snapshot if log else None


def store_response(db: DbSession, request_id: str, session_id: uuid.UUID, endpoint: str, response: dict) -> None:
    db.add(
        RequestLog(
            request_id=request_id,
            session_id=session_id,
            endpoint=endpoint,
            response_snapshot=response,
        )
    )
