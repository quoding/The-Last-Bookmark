"""턴 -> 장면·이야기 시각 매핑.

story.md 6장, ui-spec.md 6장 표를 그대로 고정한다. 서버만 이 값을 계산하며
LLM 출력에서 시각이나 장면을 추출해 덮어쓰지 않는다 (CLAUDE.md 5.1).
"""

from dataclasses import dataclass

MAX_TURNS = 12

SCENES = {
    1: {"name": "마지막 손님", "space": "서가 사이 통로"},
    2: {"name": "남겨둔 책", "space": "카운터 앞"},
    3: {"name": "쓰지 못한 한 문장", "space": "창가 작은 탁자"},
    4: {"name": "문을 닫기 전에", "space": "출입문 밖 처마 아래"},
}

INITIAL_STORY_TIME = "20:30"

# 완료 턴 -> (이야기 시각, 장면 ID)
_TURN_TABLE: dict[int, tuple[str, int]] = {
    1: ("20:32", 1),
    2: ("20:34", 1),
    3: ("20:37", 1),
    4: ("20:39", 2),
    5: ("20:41", 2),
    6: ("20:45", 2),
    7: ("20:47", 3),
    8: ("20:50", 3),
    9: ("20:53", 3),
    10: ("20:55", 4),
    11: ("20:58", 4),
    12: ("21:00", 4),
}

# 이 턴이 완료되면 다음 장면으로 전환된다 (턴 3, 6, 9에서만).
_TRANSITIONS_AFTER: dict[int, int] = {3: 2, 6: 3, 9: 4}


@dataclass(frozen=True)
class TurnInfo:
    turn: int
    story_time: str
    scene_id: int
    scene_name: str
    scene_space: str
    transitions_to: int | None  # None이면 장면 전환 없음
    is_final_turn: bool


def get_turn_info(turn: int) -> TurnInfo:
    """완료된 턴 번호(1~12)로 해당 턴의 이야기 시각과 장면을 돌려준다."""
    if turn not in _TURN_TABLE:
        raise ValueError(f"유효하지 않은 턴 번호: {turn}")
    story_time, scene_id = _TURN_TABLE[turn]
    scene = SCENES[scene_id]
    return TurnInfo(
        turn=turn,
        story_time=story_time,
        scene_id=scene_id,
        scene_name=scene["name"],
        scene_space=scene["space"],
        transitions_to=_TRANSITIONS_AFTER.get(turn),
        is_final_turn=turn == MAX_TURNS,
    )


def get_initial_scene() -> TurnInfo:
    """회차 시작 시(0턴 완료) 상태. 대화 시작 전 첫 화면에 쓴다."""
    scene = SCENES[1]
    return TurnInfo(
        turn=0,
        story_time=INITIAL_STORY_TIME,
        scene_id=1,
        scene_name=scene["name"],
        scene_space=scene["space"],
        transitions_to=None,
        is_final_turn=False,
    )
