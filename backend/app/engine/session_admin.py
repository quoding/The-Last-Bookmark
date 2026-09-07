"""회차 삭제. story.md·ui-spec.md에 없던 기능으로, 사용자 요청에 따라 추가한다.

images/sessions 사이에 순환 참조(초상화·엔딩 이미지)가 있어 단순 DELETE로는
FK 위반이 난다. 참조를 끊는 순서를 지켜 지운다. api_usage_logs는 비용 집계
기록이라 회차가 지워져도 남기고 session_id만 NULL로 비운다.
"""

from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session as DbSession

from app.models import (
    ApiUsageLog,
    Card,
    ConfirmedEvent,
    Image,
    ImageJob,
    Message,
    RequestLog,
    SceneEvent,
)
from app.models import Session as SessionModel


def delete_session(db: DbSession, session: SessionModel) -> None:
    session_id = session.id

    image_paths = [
        row[0]
        for row in db.execute(select(Image.file_path).where(Image.session_id == session_id)).all()
    ]

    # sessions -> images 참조를 먼저 끊어야 images를 지울 수 있다.
    session.portrait_image_id = None
    session.ending_image_id = None
    db.flush()

    db.execute(delete(ConfirmedEvent).where(ConfirmedEvent.session_id == session_id))
    db.execute(delete(ImageJob).where(ImageJob.session_id == session_id))
    db.execute(delete(Image).where(Image.session_id == session_id))
    db.execute(delete(Message).where(Message.session_id == session_id))
    db.execute(delete(SceneEvent).where(SceneEvent.session_id == session_id))
    db.execute(delete(Card).where(Card.session_id == session_id))
    db.execute(delete(RequestLog).where(RequestLog.session_id == session_id))
    # 비용 기록은 회차 삭제와 무관하게 남긴다. 연결만 끊는다.
    db.execute(update(ApiUsageLog).where(ApiUsageLog.session_id == session_id).values(session_id=None))

    db.delete(session)
    db.commit()

    for path_str in image_paths:
        path = Path(path_str)
        if path.exists():
            path.unlink(missing_ok=True)
