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
from app.engine.scene import get_turn_info
from app.llm.contracts import ImageSceneSpecOut
from app.models import Card, ConfirmedEvent, Message
from app.models import Session as SessionModel
from app.usage import log_llm_usage

# 근거로 보여줄 만한 이벤트 -> 결말에 어떻게 작용했는지 한 문장.
EVIDENCE_EFFECT_TEXT: dict[str, str] = {
    "book_given": "이 말이 책을 건네는 결정으로 이어졌다.",
    "book_returned": "이 말이 책을 다시 돌려주는 결정으로 이어졌다.",
    "bookmark_given": "이 말이 책갈피를 건네는 순간을 만들었다.",
    "bookmark_returned": "이 말이 책갈피를 다시 돌려주는 결정으로 이어졌다.",
    "future_plan_accepted": "이 말이 다음 만남을 약속하는 계기가 되었다.",
    "contact_exchanged": "이 말이 연락처를 주고받는 계기가 되었다.",
    "help_completed": "이 말이 정리를 함께 마무리하는 데 영향을 주었다.",
    "personal_detail_shared": "이 말이 서윤에게 오래 남을 이야기가 되었다.",
}

# 책/카드처럼 정해진 사건 4~5개 안에 personal_detail_shared까지 넣으려면 3개로는
# 부족하다. 회차마다 다른, 이 플레이어만의 엔딩을 만들려면 잡담이 아니라 실제로
# 오간 개인적인 이야기가 근거로 남아야 한다.
MAX_EVIDENCE = 5


@dataclass(frozen=True)
class EvidenceEntry:
    message_id: str
    turn: int
    story_time: str
    scene_name: str
    quote: str
    effect: str


def select_evidence(db: DbSession, session: SessionModel) -> list[EvidenceEntry]:
    """확정된 사건 중 근거로 보여줄 만한 것만, 실제 플레이어 원문과 함께 고른다.

    한 턴의 같은 발언이 여러 사건(예: 책과 책갈피를 동시에 건네는 결정)을 함께
    확정시킬 수 있다. 이때 같은 message_id로 근거를 두 번 만들지 않고, 효과
    문장을 하나로 합친다 — 그러지 않으면 같은 원문이 그대로 중복 표시된다.
    """
    confirmed = db.execute(
        select(ConfirmedEvent)
        .where(ConfirmedEvent.session_id == session.id, ConfirmedEvent.event_type.in_(EVIDENCE_EFFECT_TEXT))
        .order_by(ConfirmedEvent.turn)
    ).scalars().all()

    entries_by_message: dict[str, EvidenceEntry] = {}
    order: list[str] = []
    for event in confirmed:
        player_message = db.execute(
            select(Message)
            .where(Message.session_id == session.id, Message.turn == event.turn, Message.kind == "player")
            .order_by(Message.created_at)
        ).scalars().first()
        if player_message is None:
            continue
        message_id = str(player_message.id)
        effect = EVIDENCE_EFFECT_TEXT[event.event_type]
        if message_id in entries_by_message:
            existing = entries_by_message[message_id]
            entries_by_message[message_id] = EvidenceEntry(
                message_id=existing.message_id,
                turn=existing.turn,
                story_time=existing.story_time,
                scene_name=existing.scene_name,
                quote=existing.quote,
                effect=f"{existing.effect} {effect}",
            )
            continue
        if len(order) >= MAX_EVIDENCE:
            continue
        turn_info = get_turn_info(event.turn)
        entries_by_message[message_id] = EvidenceEntry(
            message_id=message_id,
            turn=event.turn,
            story_time=turn_info.story_time,
            scene_name=turn_info.scene_name,
            quote=player_message.text,
            effect=effect,
        )
        order.append(message_id)
    return [entries_by_message[mid] for mid in order]


# --- 엔딩 이미지 슬롯. ---
#
# 장소(location)는 더 이상 scene_id로 고정하지 않는다. 정상 완주 시 이야기는
# 항상 4번 장면(문 앞)에서 끝나므로, 장소를 서버가 고정해버리면 회차마다
# 엔딩 이미지가 "문 앞에 서 있는 장면"으로 수렴해버린다 (실사용 피드백).
# 대신 "그 직후"의 여러 순간 중 실제로 확정된 사실과 모순되지 않는 후보를
# LLM이 고르게 하고(validate_image_scene_spec), 서버는 오직 실제로 손에 든
# 물건(props)만 결정한다 — 이건 날조하면 안 되는 사실이라 LLM에 맡기지 않는다.


def compute_ending_slots(session: SessionModel, card: Card | None) -> dict[str, str]:
    """엔딩 이미지의 "사실관계" 슬롯만 결정한다. 실제로 무엇을 들고 있는지는
    LLM이 지어내면 안 되는 사실이라 서버가 직접 정한다. 장소·자세·표정·거리감은
    전부 validate_image_scene_spec()이 만드는 연출 슬롯으로 옮겼다.
    """
    if card is not None and card.written:
        props = "Holding the written card carefully"
    elif session.book_owner == "seoyun":
        props = "Holding the book in one hand, along with the keys"
    else:
        props = "Only the ring of keys in hand"

    return {"props": props}


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
# 화이트리스트+상태 전제조건으로 검증한다. 사실관계(compute_ending_slots)와
# 달리 "어디서, 어떻게 보여줄지"를 다룬다. 전제조건이 있는 축(location,
# character_action)은 실제로 확정된 사실과 모순되면 조용히 기본값으로
# 대체된다 — engine/state.py의 "허용 목록만 반영" 패턴과 동일하다. ---

CAMERA_SHOT_CHOICES = {"close", "medium", "full", "wide"}
CAMERA_ANGLE_CHOICES = {"eye_level", "slightly_high", "slightly_low", "side"}
GAZE_CHOICES = {"player", "downward", "away", "object"}
COMPOSITION_CHOICES = {"centered", "left_weighted", "right_weighted", "negative_space"}
MOOD_CHOICES = {"warm", "restrained", "unresolved", "distant", "relieved", "hopeful", "wistful"}
LIGHTING_CHOICES = {"warm_interior", "blue_rain", "mixed", "dim_closing", "streetlight"}

DEFAULT_DIRECTION: dict[str, str] = {
    "location": "still_at_the_door",
    "camera_shot": "full",
    "camera_angle": "eye_level",
    "character_action": "turning_back_for_last_look",
    "gaze": "player",
    "composition": "centered",
    "mood": "restrained",
    "lighting": "dim_closing",
}

# location마다 실제 상태와 모순되지 않는지 확인하는 조건. "그 직후"의 여러
# 순간 중 하나를 고르는 것이지, 몇 달/몇 년 뒤의 먼 미래를 그리지 않는다
# (docs/story.md 4.4, ENDING_FORBIDDEN_NOTES와 동일한 원칙).
LOCATION_REQUIREMENTS: dict[str, Callable[[SessionModel, "Card | None"], bool]] = {
    "still_at_the_door": lambda s, c: True,
    "standing_close_in_the_doorway": lambda s, c: s.player_present
    and (s.contact_exchanged or s.future_plan_accepted),
    "standing_a_step_apart_in_silence": lambda s, c: s.player_present,
    "walking_away_together_down_the_rainy_street": lambda s, c: (
        s.player_present and s.contact_exchanged and s.future_plan_accepted
    ),
    "player_already_disappearing_down_the_street": lambda s, c: not s.player_present,
    "back_inside_looking_through_the_glass": lambda s, c: not s.player_present,
    "sitting_alone_at_the_window": lambda s, c: not s.player_present,
}

# character_action마다 실제 상태와 모순되지 않는지 확인하는 조건.
CHARACTER_ACTION_REQUIREMENTS: dict[str, Callable[[SessionModel, "Card | None"], bool]] = {
    "turning_back_for_last_look": lambda s, c: True,
    "holding_the_book_close": lambda s, c: s.book_owner == "seoyun",
    "offering_the_card": lambda s, c: c is not None and c.written,
    "clutching_the_card_to_her_chest": lambda s, c: c is not None and c.written,
    "looking_down_at_the_folded_card": lambda s, c: c is not None and c.written,
    "key_ring_in_hand": lambda s, c: True,
    "adjusting_the_apron_pocket": lambda s, c: True,
    "glancing_toward_departing_player": lambda s, c: not s.player_present,
    "pausing_mid_step_to_look_back": lambda s, c: not s.player_present,
    "waving_softly": lambda s, c: s.player_present,
    "reaching_a_hand_slightly_forward": lambda s, c: s.player_present,
    "hands_empty_at_sides": lambda s, c: s.book_owner == "player" and s.bookmark_owner == "player",
    "watching_the_rain_in_silence": lambda s, c: True,
    "smiling_faintly_to_herself": lambda s, c: True,
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

    location_requirement = LOCATION_REQUIREMENTS.get(raw_spec.location)
    if location_requirement is not None and location_requirement(session, card):
        result["location"] = raw_spec.location

    action_requirement = CHARACTER_ACTION_REQUIREMENTS.get(raw_spec.character_action)
    if action_requirement is not None and action_requirement(session, card):
        result["character_action"] = raw_spec.character_action

    return result
