"""회차 삭제. story.md·ui-spec.md엔 없던 기능으로, 사용자 요청에 따라 추가한다.

장면 2~4 이미지는 BackgroundTasks로 비동기 생성되므로, 회차를 만들자마자
곧바로 지우면 그 백그라운드 작업이 삭제 도중 새 이미지 행을 커밋할 수 있다.
Python에서 자식 테이블을 순서대로 지우는 방식은 이 경합을 완전히 없애지
못한다(실측: 이미지 1장 생성에 20~30초가 걸려 재시도 창을 아무리 늘려도
따라잡기 어렵다). 대신 모든 session_id FK에 ON DELETE CASCADE(또는
SET NULL)를 걸어 DB가 원자적으로 처리하게 한다 — 세션이 지워지는 순간에
`DELETE FROM sessions` 한 문장이면 자식 행이 몇 개든, 언제 커밋됐든
Postgres가 알아서 함께 지운다. api_usage_logs만 비용 집계용이라 CASCADE
대신 SET NULL로 남긴다.
"""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models import Image
from app.models import Session as SessionModel


def delete_session(db: DbSession, session: SessionModel) -> None:
    session_id = session.id

    image_paths = [
        row[0]
        for row in db.execute(select(Image.file_path).where(Image.session_id == session_id)).all()
    ]

    db.delete(session)
    db.commit()

    for path_str in image_paths:
        path = Path(path_str)
        if path.exists():
            path.unlink(missing_ok=True)
