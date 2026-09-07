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
from app.api.deps_llm import get_llm_client
from app.api.idempotency import get_cached_response, store_response
from app.api.turns import _finalize_turn12, _get_owned_session
from app.auth import require_code_id
from app.config import get_settings
from app.db import get_db
from app.engine.scene import get_turn_info
from app.engine.state import ProposedEvent, confirm_proposed_events, record_card_for_event
from app.llm.client import LLMClient
from app.models import ConfirmedEvent, Message
from app.schemas import CardSubmitRequest, TurnResponse
from app.usage import log_llm_usage

router = APIRouter(prefix="/api")

CARD_MAX_VISIBLE_CHARS = 80


@router.post("/sessions/{session_id}/card", response_model=TurnResponse)
def submit_card(
    session_id: str,
    body: CardSubmitRequest,
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

    card = get_or_create_card(db, session.id)
    if card.decided:
        raise HTTPException(status_code=409, detail="카드는 이미 결정되었습니다.")

    if body.action not in ("write", "leave_blank"):
        raise HTTPException(status_code=422, detail="action은 'write' 또는 'leave_blank'여야 합니다.")

    if body.action == "write":
        text = body.text or ""
        if not text.strip():
            raise HTTPException(status_code=422, detail="공백만 있는 카드는 작성할 수 없습니다.")
        if len(text) > CARD_MAX_VISIBLE_CHARS:
            raise HTTPException(status_code=422, detail=f"카드는 최대 {CARD_MAX_VISIBLE_CHARS}자입니다.")
        card.written = True
        card.text = text
        card.author = "player"
        synthetic_player_input = f"(카드에 이렇게 남기기로 했다: \"{text}\")"
        record_text = f"카드에 이렇게 남겼다: \"{text}\""
    else:
        card.written = False
        card.text = None
        card.author = None
        synthetic_player_input = "(카드를 빈 채로 두기로 했다.)"
        record_text = "카드를 빈 채로 두기로 했다."

    card.decided = True

    new_turn = session.completed_turns + 1
    card.decided_turn = new_turn
    turn_info = get_turn_info(new_turn)

    recent_messages = get_recent_messages(db, session.id, before_turn=new_turn)

    db.add(Message(session_id=session.id, turn=new_turn, kind="record", record_type="memory", text=record_text))

    llm_result = llm_client.generate_turn(session, recent_messages, synthetic_player_input, card)
    log_llm_usage(db, code_id, session.id, get_settings().llm_model, llm_result.usage)
    reply_text = llm_result.output.reply
    narration_text = llm_result.output.narration

    db.add(Message(session_id=session.id, turn=new_turn, kind="reply", text=reply_text))
    if narration_text:
        db.add(Message(session_id=session.id, turn=new_turn, kind="narration", text=narration_text))

    proposed = [ProposedEvent(e.type, e.payload) for e in llm_result.output.proposed_events]
    confirmed = confirm_proposed_events(session, proposed, turn=new_turn)
    for event in confirmed:
        db.add(event)
        record = record_card_for_event(event.event_type)
        if record is not None:
            record_type, text = record
            db.add(
                Message(session_id=session.id, turn=new_turn, kind="record", record_type=record_type, text=text)
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

    store_response(db, body.request_id, session.id, "card", response.model_dump())
    db.commit()
    return response
