"""장면 엔진 뼈대 고정 테스트. ui-spec.md 6장 표를 그대로 검증한다."""

import pytest

from app.engine.scene import (
    MAX_TURNS,
    get_initial_scene,
    get_turn_info,
)

EXPECTED_TABLE = {
    1: ("20:32", 1, "마지막 손님"),
    2: ("20:34", 1, "마지막 손님"),
    3: ("20:37", 1, "마지막 손님"),
    4: ("20:39", 2, "남겨둔 책"),
    5: ("20:41", 2, "남겨둔 책"),
    6: ("20:45", 2, "남겨둔 책"),
    7: ("20:47", 3, "쓰지 못한 한 문장"),
    8: ("20:50", 3, "쓰지 못한 한 문장"),
    9: ("20:53", 3, "쓰지 못한 한 문장"),
    10: ("20:55", 4, "문을 닫기 전에"),
    11: ("20:58", 4, "문을 닫기 전에"),
    12: ("21:00", 4, "문을 닫기 전에"),
}

TRANSITION_TURNS = {3: 2, 6: 3, 9: 4}


@pytest.mark.parametrize("turn", range(1, MAX_TURNS + 1))
def test_turn_table_matches_spec(turn):
    info = get_turn_info(turn)
    expected_time, expected_scene, expected_name = EXPECTED_TABLE[turn]
    assert info.story_time == expected_time
    assert info.scene_id == expected_scene
    assert info.scene_name == expected_name


@pytest.mark.parametrize("turn", range(1, MAX_TURNS + 1))
def test_scene_transition_only_on_3_6_9(turn):
    info = get_turn_info(turn)
    if turn in TRANSITION_TURNS:
        assert info.transitions_to == TRANSITION_TURNS[turn]
    else:
        assert info.transitions_to is None


def test_only_three_transitions_total():
    transitions = [t for t in range(1, MAX_TURNS + 1) if get_turn_info(t).transitions_to is not None]
    assert transitions == [3, 6, 9]


def test_final_turn_flag():
    for t in range(1, MAX_TURNS):
        assert get_turn_info(t).is_final_turn is False
    assert get_turn_info(MAX_TURNS).is_final_turn is True


def test_initial_scene_is_scene_one_at_2030():
    initial = get_initial_scene()
    assert initial.story_time == "20:30"
    assert initial.scene_id == 1
    assert initial.turn == 0


def test_invalid_turn_raises():
    with pytest.raises(ValueError):
        get_turn_info(0)
    with pytest.raises(ValueError):
        get_turn_info(13)


def test_scene_spaces_are_distinct():
    spaces = {get_turn_info(t).scene_space for t in [1, 4, 7, 10]}
    assert len(spaces) == 4
