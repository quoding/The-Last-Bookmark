from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.common import get_or_create_card, serialize_card
from app.api.turns import _get_owned_session, _run_ending_image_job
from app.auth import require_code_id
from app.db import get_db
from app.engine.ending import DEFAULT_DIRECTION, compute_ending_slots
from app.models import Image, ImageJob
from app.schemas import EndingImageRetryResponse, EndingImageState, EndingResponse, EvidenceItem

router = APIRouter(prefix="/api")


def _ending_image_state(db: DbSession, session) -> EndingImageState:
    if session.ending_image_id is not None:
        return EndingImageState(status="done", url=f"/api/images/{session.ending_image_id}")
    job = db.execute(
        select(ImageJob)
        .where(ImageJob.session_id == session.id, ImageJob.kind == "ending")
        .order_by(ImageJob.created_at.desc())
    ).scalars().first()
    status = job.status if job else "generating"
    if status == "pending":
        status = "generating"
    return EndingImageState(status=status, url=None)


@router.get("/sessions/{session_id}/ending", response_model=EndingResponse)
def get_ending(
    session_id: str,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
):
    session = _get_owned_session(db, code_id, session_id)
    if session.status not in ("completed", "ended_early") or session.ending_title is None:
        raise HTTPException(status_code=409, detail="아직 엔딩이 생성되지 않았습니다.")

    card = get_or_create_card(db, session.id)
    evidence = [EvidenceItem(**item) for item in (session.ending_evidence or [])]

    return EndingResponse(
        title=session.ending_title,
        body=session.ending_body or "",
        card=serialize_card(card),
        evidence=evidence,
        unresolved=session.ending_unresolved or [],
        image=_ending_image_state(db, session),
    )


@router.post("/sessions/{session_id}/ending/image/retry", response_model=EndingImageRetryResponse)
def retry_ending_image(
    session_id: str,
    background_tasks: BackgroundTasks,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
):
    session = _get_owned_session(db, code_id, session_id)
    if session.status not in ("completed", "ended_early"):
        raise HTTPException(status_code=409, detail="아직 엔딩이 생성되지 않았습니다.")

    current = _ending_image_state(db, session)
    if current.status == "generating":
        raise HTTPException(status_code=409, detail="이미 그림을 만드는 중입니다.")

    card = get_or_create_card(db, session.id)
    portrait = db.get(Image, session.portrait_image_id)
    # 재시도는 LLM을 다시 부르지 않는다 — 원래 생성 때 고른 연출(camera/action 등)은
    # 저장해두지 않으므로 기본 연출로 재생성한다 (docs/PLAN_ending_image_hybrid.md 참고).
    slots = {**compute_ending_slots(session, card), **DEFAULT_DIRECTION}
    session.ending_image_id = None
    db.commit()

    background_tasks.add_task(_run_ending_image_job, session.id, portrait.file_path, slots)
    return EndingImageRetryResponse(image=EndingImageState(status="generating", url=None))
