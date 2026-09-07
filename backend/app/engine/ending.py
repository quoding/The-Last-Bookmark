"""엔딩 조립. story.md 9장·CLAUDE.md 7.5.

제목·본문·미해결 목록은 LLM이 쓰지만, 근거 인용의 원문은 DB에서 그대로
가져오고, 엔딩 이미지 슬롯은 미리 정의된 영문 조각 중에서 확정된 상태로만
고른다. 둘 다 LLM이 다시 쓰지 않는다.
"""

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.config import get_settings
from app.engine.scene import SCENES, get_turn_info
from app.llm.contracts import ImageSceneSpecOut
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
    """엔딩 이미지의 "사실관계" 슬롯만 결정한다.

    자세(posture)·표정(expression)은 더 이상 여기서 고정하지 않는다 —
    validate_image_scene_spec()이 만드는 연출 슬롯(character_action/mood 등)이
    그 역할을 대신한다. 이 함수는 실제로 무엇을 들고 있는지, 어디에
    있는지, 플레이어가 곁에 있는지처럼 서버만 결정할 수 있는 사실만 남긴다.
    """
    location = _LOCATION_BY_SCENE[session.scene_id]

    if card is not None and card.written:
        props = "Holding the written card carefully"
    elif session.book_owner == "seoyun":
        props = "Holding the book in one hand, along with the keys"
    else:
        props = "Only the ring of keys in hand"

    distance = "Standing close together" if session.player_present else "Standing alone"

    return {
        "location": location,
        "props": props,
        "distance": distance,
    }


def finalize_ending_text(
    db: DbSession, session: SessionModel, llm_client, card: Card | None = None
) -> tuple[list[EvidenceEntry], dict[str, str]]:
    """엔딩 제목·본문·미해결 목록을 확정해 session에 저장한다.

    이미지의 "사실관계" 슬롯(compute_ending_slots)은 다루지 않지만, LLM이
    함께 제안한 연출(image_scene_spec)은 여기서 검증까지 마쳐 돌려준다 —
    호출자가 compute_ending_slots()의 결과와 합쳐 최종 이미지 프롬프트를
    만든다.
    """
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
    direction = validate_image_scene_spec(session, card, result.output.image_scene_spec)
    return evidence, direction


# --- 엔딩 이미지 연출 슬롯 (image_scene_spec). LLM이 제안하지만 서버가
# 화이트리스트로 검증한다. 사실관계(compute_ending_slots)와 달리 "어떻게
# 보여줄지"만 다룬다. ---

CAMERA_SHOT_CHOICES = {"close", "medium", "full", "wide"}
CAMERA_ANGLE_CHOICES = {"eye_level", "slightly_high", "slightly_low", "side"}
GAZE_CHOICES = {"player", "downward", "away", "object"}
COMPOSITION_CHOICES = {"centered", "left_weighted", "right_weighted", "negative_space"}
MOOD_CHOICES = {"warm", "restrained", "unresolved", "distant", "relieved"}
LIGHTING_CHOICES = {"warm_interior", "blue_rain", "mixed", "dim_closing"}

DEFAULT_DIRECTION: dict[str, str] = {
    "camera_shot": "full",
    "camera_angle": "eye_level",
    "character_action": "turning_back_for_last_look",
    "gaze": "player",
    "composition": "centered",
    "mood": "restrained",
    "lighting": "dim_closing",
}

# character_action마다 실제 상태와 모순되지 않는지 확인하는 조건.
CHARACTER_ACTION_REQUIREMENTS: dict[str, Callable[[SessionModel, "Card | None"], bool]] = {
    "turning_back_for_last_look": lambda s, c: True,
    "holding_the_book_close": lambda s, c: s.book_owner == "seoyun",
    "offering_the_card": lambda s, c: c is not None and c.written,
    "key_ring_in_hand": lambda s, c: True,
    "adjusting_the_apron_pocket": lambda s, c: True,
    "glancing_toward_departing_player": lambda s, c: not s.player_present,
    "waving_softly": lambda s, c: s.player_present,
    "hands_empty_at_sides": lambda s, c: s.book_owner == "player" and s.bookmark_owner == "player",
}


def validate_image_scene_spec(
    session: SessionModel, card: Card | None, raw_spec: ImageSceneSpecOut
) -> dict[str, str]:
    """LLM이 제안한 연출 값을 화이트리스트+상태 전제조건으로 검증한다.

    후보 밖 값이거나 전제조건을 만족하지 못하면 조용히 기본값으로
    대체한다 (engine/state.py의 "허용 목록만 반영" 패턴과 동일).
    """
    result = dict(DEFAULT_DIRECTION)

    if raw_spec.camera_shot in CAMERA_SHOT_CHOICES:
        result["camera_shot"] = raw_spec.camera_shot
    if raw_spec.camera_angle in CAMERA_ANGLE_CHOICES:
        result["camera_angle"] = raw_spec.camera_angle
    if raw_spec.gaze in GAZE_CHOICES:
        result["gaze"] = raw_spec.gaze
    if raw_spec.composition in COMPOSITION_CHOICES:
        result["composition"] = raw_spec.composition
    if raw_spec.mood in MOOD_CHOICES:
        result["mood"] = raw_spec.mood
    if raw_spec.lighting in LIGHTING_CHOICES:
        result["lighting"] = raw_spec.lighting

    requirement = CHARACTER_ACTION_REQUIREMENTS.get(raw_spec.character_action)
    if requirement is not None and requirement(session, card):
        result["character_action"] = raw_spec.character_action

    return result
