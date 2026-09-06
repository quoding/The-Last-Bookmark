"""외형 프리셋. CLAUDE.md 7.2를 그대로 상수로 옮긴다.

한글 라벨과 영문 프롬프트 조각은 쌍으로 고정된 상수다. 번역 호출을 하지
않으며, 같은 선택은 항상 같은 영문을 만든다.

각 항목은 (key, 한글 라벨, 영문 조각) 튜플이다.
"""

PRESETS: dict[str, list[tuple[str, str, str]]] = {
    "hair_length": [
        ("bob", "단발", "a chin-length bob"),
        ("shoulder", "어깨 길이", "shoulder-length hair"),
        ("long", "등까지 오는 긴 머리", "long hair falling past the shoulders"),
        ("short", "짧은 층 있는 머리", "short layered hair"),
    ],
    "hair_color": [
        ("dark_brown", "짙은 갈색", "dark brown"),
        ("black", "검정", "black"),
        ("ash_brown", "애쉬 브라운", "ash brown"),
        ("auburn", "어두운 적갈색", "dark auburn"),
    ],
    "bangs": [
        ("full", "있음", "straight-across bangs"),
        ("swept", "없음(옆으로 넘긴)", "no bangs, hair swept to the side"),
        ("center", "가운데 가르마", "a center part, no bangs"),
    ],
    "eyes": [
        ("sharp", "또렷한", "clear, well-defined eyes"),
        ("droopy", "처진", "gently downturned eyes"),
        ("languid", "나른한", "relaxed, half-lidded eyes"),
        ("soft", "부드러운", "soft, rounded eyes"),
    ],
    "glasses": [
        ("round", "얇은 둥근 테", "thin round metal-framed glasses"),
        ("square", "사각 뿔테", "square tortoiseshell glasses"),
        ("none", "없음", "no glasses"),
    ],
    "impression": [
        ("calm", "차분한", "a calm, composed expression"),
        ("warm", "다정한", "a warm, gentle expression"),
        ("cool", "서늘한", "a cool, reserved expression"),
    ],
    "build": [
        ("petite", "작고 아담한", "petite and slight"),
        ("average", "보통", "average height and build"),
        ("tall", "크고 마른", "tall and slender"),
    ],
}

PRESET_AXES = tuple(PRESETS.keys())


class InvalidPresetError(ValueError):
    pass


def _lookup(axis: str, key: str) -> tuple[str, str, str]:
    for entry in PRESETS[axis]:
        if entry[0] == key:
            return entry
    raise InvalidPresetError(f"'{axis}' 축에 없는 선택지: {key}")


def validate_selection(selection: dict[str, str]) -> None:
    """7개 축이 모두 있고 각 값이 유효한 키인지 검증한다."""
    missing = [axis for axis in PRESET_AXES if axis not in selection]
    if missing:
        raise InvalidPresetError(f"선택되지 않은 항목: {', '.join(missing)}")
    for axis in PRESET_AXES:
        _lookup(axis, selection[axis])


def to_korean_summary(selection: dict[str, str]) -> str:
    """4.4의 요약 문장에 쓸 한글 라벨을 이어붙인다."""
    validate_selection(selection)
    labels = [_lookup(axis, selection[axis])[1] for axis in PRESET_AXES]
    return ", ".join(labels)


def to_english_fragments(selection: dict[str, str]) -> dict[str, str]:
    """CHARACTER 프롬프트 조립에 쓸 {axis: 영문 조각} 딕셔너리."""
    validate_selection(selection)
    return {axis: _lookup(axis, selection[axis])[2] for axis in PRESET_AXES}
