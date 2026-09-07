import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.common import (
    build_scene_state,
    get_or_create_card,
    get_recent_messages,
    is_card_available,
    serialize_message,
)
from app.api.deps import build_image_generator
from app.api.deps_llm import get_llm_client
from app.api.idempotency import get_cached_response, store_response
from app.auth import require_code_id
from app.config import get_settings
from app.db import get_db
from app.engine.ending import compute_ending_slots, finalize_ending_text
from app.engine.scene import get_turn_info
from app.engine.state import ProposedEvent, confirm_proposed_events, record_card_for_event
from app.images.openai_images import ImageGenerator
from app.images.service import generate_ending_image
from app.llm.client import LLMClient
from app.models import ConfirmedEvent, Image, ImageJob, Message
from app.models import Session as SessionModel
from app.schemas import TurnResponse, TurnSubmitRequest
from app.usage import log_llm_usage

router = APIRouter(prefix="/api")


def _get_owned_session(db: DbSession, code_id: str, session_id: str) -> SessionModel:
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="회차를 찾을 수 없습니다.")
    session = db.get(SessionModel, sid)
    if session is None or session.code_id != code_id:
        raise HTTPException(status_code=404, detail="회차를 찾을 수 없습니다.")
    return session


def _run_ending_image_job(session_id: uuid.UUID, portrait_path: str, slots: dict[str, str]):
    from app.db import get_sessionmaker

    db = get_sessionmaker()()
    session_row = db.get(SessionModel, session_id)
    if session_row is None:
        db.close()
        return  # 회차가 삭제된 뒤 실행됐다. 조용히 종료한다.
    generator = build_image_generator(session_row.code_id)
    try:
        try:
            job = ImageJob(session_id=session_id, kind="ending", scene_id=None, status="pending")
            db.add(job)
            db.flush()
        except Exception:  # noqa: BLE001 - 그 사이 회차가 지워졌으면 여기서 멈춘다
            db.rollback()
            return
        try:
            image = generate_ending_image(db, generator, session_id, portrait_path, slots, session_row.code_id)
            job.status = "done"
            job.image_id = image.id
            session = db.get(SessionModel, session_id)
            if session is not None:
                session.ending_image_id = image.id
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error = str(exc)
        try:
            db.commit()
        except Exception:  # noqa: BLE001 - 그 사이 회차가 지워졌으면 이 작업 결과는 버린다
            db.rollback()
    finally:
        db.close()


def _finalize_turn12(
    db: DbSession,
    session: SessionModel,
    llm_client: LLMClient,
    background_tasks: BackgroundTasks,
    turn: int,
):
    session.door_locked = True
    db.add(ConfirmedEvent(session_id=session.id, turn=turn, event_type="door_locked", payload={}))
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)

    card = get_or_create_card(db, session.id)
    _evidence, direction = finalize_ending_text(db, session, llm_client, card)
    db.flush()

    portrait = db.get(Image, session.portrait_image_id)
    slots = {**compute_ending_slots(session, card), **direction}
    background_tasks.add_task(_run_ending_image_job, session.id, portrait.file_path, slots)


@router.post("/sessions/{session_id}/turns", response_model=TurnResponse)
def submit_turn(
    session_id: str,
    body: TurnSubmitRequest,
    background_tasks: BackgroundTasks,
    code_id: str = Depends(require_code_id),
    db: DbSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
):
    session = _get_owned_session(db, code_id, session_id)

    cached = get_cached_response(db, body.request_id)
    if cached is not None:
        return TurnResponse(**cached)

    if session.status != "in_progress":
        raise HTTPException(status_code=409, detail="이미 종료된 회차입니다.")
    if session.completed_turns >= 12:
        raise HTTPException(status_code=409, detail="더 이상 진행할 턴이 없습니다.")
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="빈 입력은 보낼 수 없습니다.")

    new_turn = session.completed_turns + 1
    turn_info = get_turn_info(new_turn)

    recent_messages = get_recent_messages(db, session.id, before_turn=new_turn)
    card = get_or_create_card(db, session.id)

    player_message = Message(session_id=session.id, turn=new_turn, kind="player", text=body.text)
    db.add(player_message)
    db.flush()

    llm_result = llm_client.generate_turn(session, recent_messages, body.text, card)
    log_llm_usage(db, code_id, session.id, get_settings().llm_model, llm_result.usage)
    reply_text = llm_result.output.reply
    narration_text = llm_result.output.narration

    db.add(Message(session_id=session.id, turn=new_turn, kind="reply", text=reply_text))
    if narration_text:
        db.add(Message(session_id=session.id, turn=new_turn, kind="narration", text=narration_text))

    proposed = [ProposedEvent(e.type, e.payload) for e in llm_result.output.proposed_events]
    confirmed = confirm_proposed_events(session, proposed, turn=new_turn)
    for event in confirmed:
        event.source_message_id = player_message.id
        db.add(event)
        record = record_card_for_event(event.event_type)
        if record is not None:
            record_type, text = record
            db.add(
                Message(
                    session_id=session.id,
                    turn=new_turn,
                    kind="record",
                    record_type=record_type,
                    text=text,
                )
            )

    session.completed_turns = new_turn
    session.story_time = turn_info.story_time
    session.scene_id = turn_info.transitions_to if turn_info.transitions_to else turn_info.scene_id

    if turn_info.is_final_turn:
        _finalize_turn12(db, session, llm_client, background_tasks, new_turn)

    db.flush()

    turn_messages = list(
        db.execute(
            select(Message)
            .where(Message.session_id == session.id, Message.turn == new_turn)
            .order_by(Message.created_at)
        ).scalars().all()
    )

    if turn_info.transitions_to:
        scene_state = build_scene_state(db, session.id, turn_info.transitions_to, entered=True)
    else:
        scene_state = build_scene_state(db, session.id, turn_info.scene_id, entered=False)

    response = TurnResponse(
        messages=[serialize_message(m) for m in turn_messages],
        completed_turns=new_turn,
        story_time=turn_info.story_time,
        scene=scene_state,
        card_available=is_card_available(session, card),
        is_final_turn=turn_info.is_final_turn,
    )

    store_response(db, body.request_id, session.id, "turns", response.model_dump())
    db.commit()
    return response
