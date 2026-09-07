"""엔딩 조립. story.md 9장·CLAUDE.md 7.5.

제목·본문·미해결 목록은 LLM이 쓰지만, 근거 인용의 원문은 DB에서 그대로
가져오고, 엔딩 이미지 슬롯은 미리 정의된 영문 조각 중에서 확정된 상태로만
고른다. 둘 다 LLM이 다시 쓰지 않는다.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.config import get_settings
from app.engine.scene import SCENES, get_turn_info
from app.models import Card, ConfirmedEvent, Message
from app.models import Session as SessionModel
from app.usage import log_llm_usage

# 근거로 보여줄 만한 이벤트 -> 결말에 어떻게 작용했는지 한 문장.
EVIDENCE_EFFECT_TEXT: dict[str, str] = {
    "book_given": "이 말이 책을 건네는 결정으로 이어졌다.",
    "bookmark_given": "이 말이 책갈피를 건네는 순간을 만들었다.",
    "future_plan_accepted": "이 말이 다음 만남을 약속하는 계기가 되었다.",
    "contact_exchanged": "이 말이 연락처를 주고받는 계기가 되었다.",
    "help_completed": "이 말이 정리를 함께 마무리하는 데 영향을 주었다.",
}

MAX_EVIDENCE = 3


@dataclass(frozen=True)
class EvidenceEntry:
    message_id: str
    turn: int
    story_time: str
    scene_name: str
    quote: str
    effect: str


def select_evidence(db: DbSession, session: SessionModel) -> list[EvidenceEntry]:
    """확정된 사건 중 근거로 보여줄 만한 것만, 실제 플레이어 원문과 함께 고른다."""
    confirmed = db.execute(
        select(ConfirmedEvent)
        .where(ConfirmedEvent.session_id == session.id, ConfirmedEvent.event_type.in_(EVIDENCE_EFFECT_TEXT))
        .order_by(ConfirmedEvent.turn)
    ).scalars().all()

    entries: list[EvidenceEntry] = []
    for event in confirmed:
        if len(entries) >= MAX_EVIDENCE:
            break
        player_message = db.execute(
            select(Message)
            .where(Message.session_id == session.id, Message.turn == event.turn, Message.kind == "player")
            .order_by(Message.created_at)
        ).scalars().first()
        if player_message is None:
            continue
        turn_info = get_turn_info(event.turn)
        entries.append(
            EvidenceEntry(
                message_id=str(player_message.id),
                turn=event.turn,
                story_time=turn_info.story_time,
                scene_name=turn_info.scene_name,
                quote=player_message.text,
                effect=EVIDENCE_EFFECT_TEXT[event.event_type],
            )
        )
    return entries


# --- 엔딩 이미지 슬롯. CLAUDE.md 7.5. 모두 미리 정의된 영문 조각이다. ---

_LOCATION_BY_SCENE = {
    1: "In the narrow aisle between the bookshelves",
    2: "Behind the shop counter",
    3: "At the small table by the front window",
    4: "Under the awning outside the shop, the door locked behind her",
}


def compute_ending_slots(session: SessionModel, card: Card | None) -> dict[str, str]:
    location = _LOCATION_BY_SCENE[session.scene_id]

    posture = "Turning back for one last look" if session.door_locked else "Still standing where the conversation stopped"

    if session.future_plan_accepted:
        expression = "A careful, hopeful smile"
    elif session.contact_exchanged:
        expression = "A soft, quiet smile"
    elif session.book_owner == "player" or session.bookmark_owner == "player":
        expression = "A calm, grateful expression"
    else:
        expression = "A composed, quiet expression"

    if card is not None and card.written:
        props = "Holding the written card carefully"
    elif session.book_owner == "seoyun":
        props = "Holding the book in one hand, along with the keys"
    else:
        props = "Only the ring of keys in hand"

    distance = "Standing close together" if session.player_present else "Standing alone"

    return {
        "location": location,
        "posture": posture,
        "expression": expression,
        "props": props,
        "distance": distance,
    }


def finalize_ending_text(db: DbSession, session: SessionModel, llm_client, card: Card | None = None) -> list[EvidenceEntry]:
    """엔딩 제목·본문·미해결 목록을 확정해 session에 저장한다. 이미지는 다루지 않는다."""
    evidence = select_evidence(db, session)
    quotes = [e.quote for e in evidence]
    result = llm_client.generate_ending(session, quotes, card)
    log_llm_usage(db, session.code_id, session.id, get_settings().llm_model, result.usage)

    session.ending_title = result.output.title
    session.ending_body = result.output.body
    session.ending_unresolved = result.output.unresolved
    session.ending_evidence = [
        {
            "message_id": e.message_id,
            "turn": e.turn,
            "story_time": e.story_time,
            "scene_name": e.scene_name,
            "quote": e.quote,
            "effect": e.effect,
        }
        for e in evidence
    ]
    return evidence
