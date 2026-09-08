"""엔딩 이미지 하이브리드 연출(image_scene_spec) 검증 로직.

docs/PLAN_ending_image_hybrid.md의 하이브리드 구조: 서버가 사실관계
(compute_ending_slots)를 결정하고, LLM이 제안한 연출(image_scene_spec)은
화이트리스트+상태 전제조건으로 검증한 뒤에만 반영한다.
"""

from app.engine.ending import DEFAULT_DIRECTION, compute_ending_slots, validate_image_scene_spec
from app.llm.contracts import ImageSceneSpecOut
from app.models import Card


def _spec(**overrides) -> ImageSceneSpecOut:
    base = dict(
        location="still_at_the_door",
        camera_shot="medium",
        camera_angle="slightly_low",
        character_action="turning_back_for_last_look",
        gaze="downward",
        composition="left_weighted",
        mood="warm",
        lighting="warm_interior",
    )
    base.update(overrides)
    return ImageSceneSpecOut(**base)


def test_valid_spec_is_used_as_is(make_session):
    session = make_session()
    result = validate_image_scene_spec(session, None, _spec())
    assert result["location"] == "still_at_the_door"
    assert result["camera_shot"] == "medium"
    assert result["camera_angle"] == "slightly_low"
    assert result["gaze"] == "downward"
    assert result["composition"] == "left_weighted"
    assert result["mood"] == "warm"
    assert result["lighting"] == "warm_interior"


def test_location_requires_player_present_and_mutual_commitment(make_session):
    session_no_commitment = make_session(player_present=True, contact_exchanged=False, future_plan_accepted=False)
    result = validate_image_scene_spec(
        session_no_commitment, None, _spec(location="walking_away_together_down_the_rainy_street")
    )
    assert result["location"] == DEFAULT_DIRECTION["location"]

    session_committed = make_session(
        index=2, player_present=True, contact_exchanged=True, future_plan_accepted=True
    )
    result2 = validate_image_scene_spec(
        session_committed, None, _spec(location="walking_away_together_down_the_rainy_street")
    )
    assert result2["location"] == "walking_away_together_down_the_rainy_street"


def test_location_requires_player_departed_for_departure_variants(make_session):
    session_present = make_session(player_present=True)
    result = validate_image_scene_spec(
        session_present, None, _spec(location="player_already_disappearing_down_the_street")
    )
    assert result["location"] == DEFAULT_DIRECTION["location"]

    session_departed = make_session(index=2, player_present=False)
    result2 = validate_image_scene_spec(
        session_departed, None, _spec(location="sitting_alone_at_the_window")
    )
    assert result2["location"] == "sitting_alone_at_the_window"


def test_unknown_location_falls_back_to_default(make_session):
    session = make_session()
    result = validate_image_scene_spec(session, None, _spec(location="on_the_moon"))
    assert result["location"] == DEFAULT_DIRECTION["location"]


def test_out_of_whitelist_values_fall_back_to_default(make_session):
    session = make_session()
    spec = _spec(camera_shot="drone_shot", mood="euphoric", lighting="neon")
    result = validate_image_scene_spec(session, None, spec)
    assert result["camera_shot"] == DEFAULT_DIRECTION["camera_shot"]
    assert result["mood"] == DEFAULT_DIRECTION["mood"]
    assert result["lighting"] == DEFAULT_DIRECTION["lighting"]


def test_empty_spec_falls_back_entirely_to_default(make_session):
    session = make_session()
    result = validate_image_scene_spec(session, None, ImageSceneSpecOut())
    assert result == DEFAULT_DIRECTION


def test_character_action_requires_book_not_yet_given(make_session):
    session = make_session(book_owner="seoyun")
    result = validate_image_scene_spec(session, None, _spec(character_action="holding_the_book_close"))
    assert result["character_action"] == "holding_the_book_close"

    session2 = make_session(index=2, book_owner="player")
    result2 = validate_image_scene_spec(session2, None, _spec(character_action="holding_the_book_close"))
    assert result2["character_action"] == DEFAULT_DIRECTION["character_action"]


def test_character_action_requires_written_card(make_session):
    session = make_session()
    card_unwritten = Card(session_id=session.id, decided=True, written=False)
    result = validate_image_scene_spec(session, card_unwritten, _spec(character_action="offering_the_card"))
    assert result["character_action"] == DEFAULT_DIRECTION["character_action"]

    card_written = Card(session_id=session.id, decided=True, written=True, text="고마웠어요.", author="player")
    result2 = validate_image_scene_spec(session, card_written, _spec(character_action="offering_the_card"))
    assert result2["character_action"] == "offering_the_card"


def test_character_action_requires_player_departed(make_session):
    session_present = make_session(player_present=True)
    result = validate_image_scene_spec(
        session_present, None, _spec(character_action="glancing_toward_departing_player")
    )
    assert result["character_action"] == DEFAULT_DIRECTION["character_action"]

    session_departed = make_session(index=2, player_present=False)
    result2 = validate_image_scene_spec(
        session_departed, None, _spec(character_action="glancing_toward_departing_player")
    )
    assert result2["character_action"] == "glancing_toward_departing_player"


def test_character_action_requires_both_items_given(make_session):
    session_partial = make_session(book_owner="player", bookmark_owner="seoyun")
    result = validate_image_scene_spec(session_partial, None, _spec(character_action="hands_empty_at_sides"))
    assert result["character_action"] == DEFAULT_DIRECTION["character_action"]

    session_both = make_session(index=2, book_owner="player", bookmark_owner="player")
    result2 = validate_image_scene_spec(session_both, None, _spec(character_action="hands_empty_at_sides"))
    assert result2["character_action"] == "hands_empty_at_sides"


def test_compute_ending_slots_only_returns_props(make_session):
    """location·character_action·distance는 전부 validate_image_scene_spec()으로
    옮겨졌다 — compute_ending_slots()는 서버가 날조하면 안 되는 사실(props)만 남긴다."""
    session = make_session(scene_id=4, player_present=True, book_owner="seoyun")
    slots = compute_ending_slots(session, None)
    assert set(slots.keys()) == {"props"}


def test_merged_slots_cover_full_ending_prompt_signature(make_session):
    from app.images.prompts import ending_prompt

    session = make_session(scene_id=4, player_present=True, book_owner="seoyun")
    facts = compute_ending_slots(session, None)
    direction = validate_image_scene_spec(session, None, _spec())
    merged = {**facts, **direction}
    prompt = ending_prompt(**merged)  # 인자 누락/중복 없이 조립되면 성공
    assert isinstance(prompt, str) and len(prompt) > 0
