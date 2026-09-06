"""이미지 프롬프트 조립. CLAUDE.md 7.3~7.5를 그대로 옮긴다.

STYLE + CHARACTER/REFERENCE + SCENE + NEGATIVE 3~4단 구조로 조립하며,
사용자 입력이나 LLM 자유 생성 텍스트가 섞이는 경로는 없다 (CLAUDE.md 5.5).
"""

STYLE_BLOCK = (
    "Soft 2D anime-style romance illustration, restrained and painterly. "
    "Muted, low-saturation palette. Warm indoor lighting with cool blue night "
    "tones outside. Gentle linework, no harsh contrast. Vertical composition, "
    "full-body framing with headroom."
)

NEGATIVE_BLOCK = (
    "No readable text anywhere. No signage, no book titles, no handwriting. "
    "No other people in frame. No modern logos or brand marks."
)

_CHARACTER_TEMPLATE = (
    "A 27-year-old Korean woman, a quiet independent bookstore owner. "
    "{hair_length}, {hair_color} hair, {bangs}. {eyes}. {glasses}. "
    "{impression}. {build}. "
    "She wears a cream-colored knit sweater and a dark green apron, "
    "with a small silver pen in the apron's left pocket."
)

REFERENCE_SUMMARY = (
    "The same woman as in the reference image, wearing the same cream knit "
    "sweater and dark green apron."
)

SCENE_PROMPTS: dict[int, str] = {
    1: (
        "Standing in a narrow aisle between wooden bookshelves, "
        "cardboard packing boxes on the floor around her. "
        "She has just set down a box and is turning to look toward "
        "the viewer, a faint tired smile. Warm ceiling lights, "
        "shelves half-empty."
    ),
    2: (
        "Standing behind the shop counter, a single short story "
        "collection in her hands with a frayed navy-blue cloth "
        "bookmark tucked into it. A small desk lamp on the counter "
        "lights the book from the side. She is offering it forward."
    ),
    3: (
        "Seated at a small table by the front window, a blank cream "
        "card and a silver pen in front of her. Rain streaks the glass; "
        "cool blue light from outside mixes with the warm interior lamp. "
        "She rests her chin lightly on one hand, thinking."
    ),
    4: (
        "Standing outside the shop entrance under the awning at night, "
        "the darkened storefront behind her, a ring of keys in her hand. "
        "Streetlight and wet pavement reflections light her from the "
        "front. Light rain. She has just turned back from the locked door."
    ),
}

_ENDING_TEMPLATE = "{location}. {posture}. {expression}. {props}. {distance}."


def character_fragment(fragments: dict[str, str]) -> str:
    return _CHARACTER_TEMPLATE.format(**fragments)


def portrait_prompt(fragments: dict[str, str]) -> str:
    return "\n\n".join([STYLE_BLOCK, character_fragment(fragments), NEGATIVE_BLOCK])


def scene_prompt(scene_id: int) -> str:
    if scene_id not in SCENE_PROMPTS:
        raise ValueError(f"유효하지 않은 장면 번호: {scene_id}")
    return "\n\n".join([STYLE_BLOCK, REFERENCE_SUMMARY, SCENE_PROMPTS[scene_id], NEGATIVE_BLOCK])


def ending_prompt(location: str, posture: str, expression: str, props: str, distance: str) -> str:
    """확정된 슬롯 값(모두 미리 정의된 영문 조각)으로 엔딩 이미지 프롬프트를 채운다."""
    filled = _ENDING_TEMPLATE.format(
        location=location, posture=posture, expression=expression, props=props, distance=distance
    )
    return "\n\n".join([STYLE_BLOCK, REFERENCE_SUMMARY, filled, NEGATIVE_BLOCK])
