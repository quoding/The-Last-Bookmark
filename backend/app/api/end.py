from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from app.api.common import get_or_create_card
from app.api.deps_llm import get_llm_client
from app.api.idempotency import get_cached_response, store_response
from app.api.turns import _get_owned_session, _run_ending_image_job
from app.auth import require_code_id
from app.db import get_db
from app.engine.ending import compute_ending_slots, finalize_ending_text
from app.llm.client import LLMClient
from app.models import Image
from app.schemas import EndEarlyRequest, EndEarlyResponse

router = APIRouter(prefix="/api")


@router.post("/sessions/{session_id}/end", response_model=EndEarlyResponse)
def end_early(
    session_id: str,
    body: EndEarlyRequest,
    background_tasks: BackgroundTasks,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
):
    """메뉴를 통한 조기 종료 (ui-spec.md 5.6). 작별 대사를 새로 만들지 않고,
    지금까지 확정된 사건만으로 엔딩을 생성한다. 문 잠금은 확정하지 않는다."""
    session = _get_owned_session(db, code_id, session_id)

    cached = get_cached_response(db, body.request_id)
    if cached is not None:
        return EndEarlyResponse(**cached)

    if session.status != "in_progress":
        raise HTTPException(status_code=409, detail="이미 종료된 회차입니다.")

    session.status = "ended_early"
    session.completed_at = datetime.now(timezone.utc)

    card = get_or_create_card(db, session.id)
    finalize_ending_text(db, session, llm_client, card)
    db.flush()

    portrait = db.get(Image, session.portrait_image_id)
    slots = compute_ending_slots(session, card)
    background_tasks.add_task(_run_ending_image_job, session.id, portrait.file_path, slots)

    response = EndEarlyResponse(status="ended_early")
    store_response(db, body.request_id, session.id, "end", response.model_dump())
    db.commit()
    return response
