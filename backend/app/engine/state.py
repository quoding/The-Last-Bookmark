"""확정 사건 관리. CLAUDE.md 5.1의 핵심 규칙을 구현한다.

LLM이 제안한 proposed_events는 제안일 뿐이다. 여기 정의된 허용 목록에
있는 전이만, 그것도 현재 상태에서 실제로 가능할 때만 서버가 확정한다.
사용자가 무엇을 입력했든("우리는 이미 사귀는 사이야") 이 파일을 거치지
않고는 세계 상태가 바뀌지 않는다.
"""

from dataclasses import dataclass
from typing import Callable

from app.models import ConfirmedEvent, Session

# event_type -> (record_type 또는 None, 시스템 기록 카드 문구 또는 None)
# record_type: promise / fact / memory. None이면 시스템 기록 카드를 만들지 않는다.
RECORD_TEMPLATES: dict[str, tuple[str | None, str | None]] = {
    "help_offered": (None, None),
    "help_completed": ("memory", "함께 정리를 도왔다"),
    "book_given": ("memory", "서윤이 마지막으로 골라둔 책을 건넸다"),
    "book_declined": (None, None),
    "bookmark_given": ("memory", "파란 책갈피가 당신에게 건네졌다"),
    "future_plan_proposed": (None, None),
    "future_plan_accepted": ("promise", "다음 만남을 약속했다"),
    "contact_exchanged": ("fact", "연락할 방법을 주고받았다"),
    "player_departed": (None, None),
}


@dataclass(frozen=True)
class ProposedEvent:
    event_type: str
    payload: dict


def _apply_help_offered(session: Session, payload: dict) -> bool:
    if session.help_status == "not_offered":
        session.help_status = "offered"
        return True
    return False


def _apply_help_completed(session: Session, payload: dict) -> bool:
    if session.help_status in ("not_offered", "offered"):
        session.help_status = "helped"
        return True
    return False


def _apply_book_given(session: Session, payload: dict) -> bool:
    if session.scene_id >= 2 and session.book_owner == "seoyun":
        session.book_owner = "player"
        return True
    return False


def _apply_book_declined(session: Session, payload: dict) -> bool:
    return session.scene_id >= 2 and session.book_owner == "seoyun"


def _apply_bookmark_given(session: Session, payload: dict) -> bool:
    if session.scene_id >= 2 and session.bookmark_owner == "seoyun":
        session.bookmark_owner = "player"
        return True
    return False


def _apply_future_plan_proposed(session: Session, payload: dict) -> bool:
    text = payload.get("text")
    if not text or not isinstance(text, str):
        return False
    if session.future_plan_accepted:
        return False  # 이미 합의된 약속은 새 제안으로 덮어쓰지 않는다
    session.future_plan = text
    return True


def _apply_future_plan_accepted(session: Session, payload: dict) -> bool:
    if session.future_plan and not session.future_plan_accepted:
        session.future_plan_accepted = True
        return True
    return False


def _apply_contact_exchanged(session: Session, payload: dict) -> bool:
    if not session.contact_exchanged:
        session.contact_exchanged = True
        return True
    return False


def _apply_player_departed(session: Session, payload: dict) -> bool:
    if session.player_present:
        session.player_present = False
        return True
    return False


APPLIERS: dict[str, Callable[[Session, dict], bool]] = {
    "help_offered": _apply_help_offered,
    "help_completed": _apply_help_completed,
    "book_given": _apply_book_given,
    "book_declined": _apply_book_declined,
    "bookmark_given": _apply_bookmark_given,
    "future_plan_proposed": _apply_future_plan_proposed,
    "future_plan_accepted": _apply_future_plan_accepted,
    "contact_exchanged": _apply_contact_exchanged,
    "player_departed": _apply_player_departed,
}


def confirm_proposed_events(
    session: Session,
    proposed: list[ProposedEvent],
    turn: int,
) -> list[ConfirmedEvent]:
    """허용 목록에 있고 현재 상태에서 유효한 제안만 확정해 돌려준다.

    허용되지 않거나 전제조건이 안 맞는 제안은 조용히 버린다. 사용자에게
    오류를 보여주지 않는다 (CLAUDE.md 8.2/8.3).
    """
    confirmed: list[ConfirmedEvent] = []
    for event in proposed:
        applier = APPLIERS.get(event.event_type)
        if applier is None:
            continue
        if applier(session, event.payload):
            confirmed.append(
                ConfirmedEvent(
                    session_id=session.id,
                    turn=turn,
                    event_type=event.event_type,
                    payload=event.payload,
                )
            )
    return confirmed


def record_card_for_event(event_type: str) -> tuple[str, str] | None:
    """이벤트가 시스템 기록 카드를 만들어야 하면 (record_type, 문구)를 돌려준다."""
    record_type, text = RECORD_TEMPLATES.get(event_type, (None, None))
    if record_type is None:
        return None
    return record_type, text
