"""CLAUDE.md 5.1 — 허용 목록에 있는 전이만 확정된다. story.md 13장 경로 E 검증."""

import uuid

from app.engine.state import ProposedEvent, confirm_proposed_events
from app.models import Session


def _fresh_session(**overrides) -> Session:
    defaults = dict(
        id=uuid.uuid4(),
        code_id="test",
        index=1,
        presets={},
        scene_id=2,
        help_status="not_offered",
        book_owner="seoyun",
        bookmark_owner="seoyun",
        future_plan=None,
        future_plan_accepted=False,
        contact_exchanged=False,
        player_present=True,
        door_locked=False,
    )
    defaults.update(overrides)
    return Session(**defaults)


def test_unknown_event_type_is_silently_dropped():
    session = _fresh_session()
    confirmed = confirm_proposed_events(
        session, [ProposedEvent("world_reopened_and_they_are_dating", {})], turn=5
    )
    assert confirmed == []
    assert session.door_locked is False


def test_player_claiming_world_state_does_not_change_facts():
    """경로 E: 플레이어가 '우리는 이미 사귀는 사이야'라고 말해도 허용 목록 밖 이벤트는 반영되지 않는다."""
    session = _fresh_session(book_owner="seoyun", bookmark_owner="seoyun")
    confirmed = confirm_proposed_events(
        session,
        [
            ProposedEvent("relationship_confirmed_dating", {}),
            ProposedEvent("book_given", {}),  # 이건 허용 목록에 있지만 전제조건을 봐야 한다
        ],
        turn=5,
    )
    assert session.book_owner == "player"  # scene_id>=2라 실제로 허용됨
    types = {c.event_type for c in confirmed}
    assert "relationship_confirmed_dating" not in types
    assert "book_given" in types


def test_book_given_requires_scene_two_or_later():
    session = _fresh_session(scene_id=1, book_owner="seoyun")
    confirmed = confirm_proposed_events(session, [ProposedEvent("book_given", {})], turn=2)
    assert confirmed == []
    assert session.book_owner == "seoyun"


def test_book_given_is_idempotent_once_owned_by_player():
    session = _fresh_session(scene_id=2, book_owner="player")
    confirmed = confirm_proposed_events(session, [ProposedEvent("book_given", {})], turn=5)
    assert confirmed == []


def test_future_plan_accepted_requires_a_proposal_first():
    session = _fresh_session()
    confirmed = confirm_proposed_events(session, [ProposedEvent("future_plan_accepted", {})], turn=8)
    assert confirmed == []
    assert session.future_plan_accepted is False


def test_future_plan_propose_then_accept():
    session = _fresh_session()
    confirm_proposed_events(
        session, [ProposedEvent("future_plan_proposed", {"text": "다음에 또 봐요"})], turn=8
    )
    assert session.future_plan == "다음에 또 봐요"
    assert session.future_plan_accepted is False

    confirmed = confirm_proposed_events(session, [ProposedEvent("future_plan_accepted", {})], turn=9)
    assert session.future_plan_accepted is True
    assert confirmed[0].event_type == "future_plan_accepted"


def test_accepted_plan_is_not_overwritten_by_new_proposal():
    session = _fresh_session(future_plan="원래 약속", future_plan_accepted=True)
    confirm_proposed_events(
        session, [ProposedEvent("future_plan_proposed", {"text": "다른 약속"})], turn=10
    )
    assert session.future_plan == "원래 약속"


def test_door_locked_is_never_settable_via_proposed_event():
    """door_locked은 서버가 12턴 완료 시 직접 확정하며 LLM 제안 경로가 아예 없다."""
    session = _fresh_session()
    confirm_proposed_events(session, [ProposedEvent("door_locked", {})], turn=12)
    assert session.door_locked is False


def test_personal_detail_shared_always_confirms_without_changing_state():
    session = _fresh_session()
    confirmed = confirm_proposed_events(
        session, [ProposedEvent("personal_detail_shared", {})], turn=3
    )
    assert {c.event_type for c in confirmed} == {"personal_detail_shared"}
    # 세계 상태(사실관계)는 전혀 안 바뀐다 — 근거로 남기기 위한 표시일 뿐이다.
    assert session.book_owner == "seoyun"
    assert session.bookmark_owner == "seoyun"
    assert session.door_locked is False


def test_book_returned_requires_player_to_own_it_first():
    session = _fresh_session(book_owner="seoyun")
    confirmed = confirm_proposed_events(session, [ProposedEvent("book_returned", {})], turn=6)
    assert confirmed == []
    assert session.book_owner == "seoyun"


def test_book_returned_gives_book_back_to_seoyun():
    session = _fresh_session(book_owner="player")
    confirmed = confirm_proposed_events(session, [ProposedEvent("book_returned", {})], turn=6)
    assert session.book_owner == "seoyun"
    assert {c.event_type for c in confirmed} == {"book_returned"}


def test_book_can_round_trip_given_then_returned_then_given_again():
    session = _fresh_session(scene_id=2, book_owner="seoyun")
    confirm_proposed_events(session, [ProposedEvent("book_given", {})], turn=4)
    assert session.book_owner == "player"
    confirm_proposed_events(session, [ProposedEvent("book_returned", {})], turn=6)
    assert session.book_owner == "seoyun"
    confirm_proposed_events(session, [ProposedEvent("book_given", {})], turn=8)
    assert session.book_owner == "player"


def test_bookmark_declined_requires_seoyun_still_owns_it():
    session = _fresh_session(scene_id=2, bookmark_owner="player")
    confirmed = confirm_proposed_events(session, [ProposedEvent("bookmark_declined", {})], turn=5)
    assert confirmed == []


def test_bookmark_returned_gives_bookmark_back_to_seoyun():
    session = _fresh_session(bookmark_owner="player")
    confirmed = confirm_proposed_events(session, [ProposedEvent("bookmark_returned", {})], turn=6)
    assert session.bookmark_owner == "seoyun"
    assert {c.event_type for c in confirmed} == {"bookmark_returned"}


def test_bookmark_returned_requires_player_to_own_it_first():
    session = _fresh_session(bookmark_owner="seoyun")
    confirmed = confirm_proposed_events(session, [ProposedEvent("bookmark_returned", {})], turn=6)
    assert confirmed == []
    assert session.bookmark_owner == "seoyun"
