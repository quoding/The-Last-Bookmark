"""이미지 프롬프트 조립. CLAUDE.md 7.3~7.5를 그대로 옮긴다.

STYLE + CHARACTER/REFERENCE + SCENE + NEGATIVE 3~4단 구조로 조립하며,
사용자 입력이나 LLM 자유 생성 텍스트가 섞이는 경로는 없다 (CLAUDE.md 5.5).
"""

STYLE_BLOCK_BASE = (
    "Soft 2D anime-style romance illustration, restrained and painterly. "
    "Muted, low-saturation palette. Warm indoor lighting with cool blue night "
    "tones outside. Gentle linework, no harsh contrast. Vertical composition."
)

STYLE_FRAMING_DEFAULT = "Full-body framing with headroom."

STYLE_BLOCK = f"{STYLE_BLOCK_BASE} {STYLE_FRAMING_DEFAULT}"

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

# --- 엔딩 이미지 연출 슬롯(image_scene_spec) -> 영문 문구 매핑.
# 키는 engine/ending.py의 화이트리스트(CAMERA_SHOT_CHOICES 등)와 1:1로
# 대응한다. 여기 없는 키가 들어오면 KeyError로 즉시 드러나게 둔다 —
# 화이트리스트 검증은 engine/ending.py가 이미 끝낸 뒤이므로 여기서
# 조용히 넘어가면 안 된다.

CAMERA_SHOT_PHRASES = {
    "close": "Close-up shot framing her face and shoulders",
    "medium": "Medium shot from the waist up",
    "full": "Full-body vertical framing with headroom",
    "wide": "Wide shot showing her small within the surrounding space",
}

CAMERA_ANGLE_PHRASES = {
    "eye_level": "at eye level",
    "slightly_high": "from a slightly high angle looking down at her",
    "slightly_low": "from a slightly low angle looking up at her",
    "side": "from the side, in profile",
}

CHARACTER_ACTION_PHRASES = {
    "turning_back_for_last_look": "She has turned back for one last look",
    "holding_the_book_close": "She is holding the book close, not yet handed over",
    "offering_the_card": "She is holding the written card gently",
    "key_ring_in_hand": "She holds a small ring of keys",
    "adjusting_the_apron_pocket": "She is adjusting the pen in her apron pocket",
    "glancing_toward_departing_player": "She glances toward the door the player has already left through",
    "waving_softly": "She raises a hand in a small, soft wave",
    "hands_empty_at_sides": "Her hands rest empty at her sides",
}

GAZE_PHRASES = {
    "player": "looking toward the viewer",
    "downward": "looking down",
    "away": "looking away, off to the side",
    "object": "looking down at what she is holding",
}

COMPOSITION_PHRASES = {
    "centered": "She is centered in the frame",
    "left_weighted": "She is positioned toward the left of the frame, with negative space on the right",
    "right_weighted": "She is positioned toward the right of the frame, with negative space on the left",
    "negative_space": "She occupies only a small part of the frame, surrounded by open space",
}

MOOD_PHRASES = {
    "warm": "The overall mood is warm and settled",
    "restrained": "The overall mood is quiet and restrained",
    "unresolved": "The overall mood feels unresolved and a little uncertain",
    "distant": "The overall mood feels distant and reserved",
    "relieved": "The overall mood feels quietly relieved",
}

LIGHTING_PHRASES = {
    "warm_interior": "lit by warm interior lamplight",
    "blue_rain": "lit by cool blue light from the rain outside",
    "mixed": "lit by a mix of warm interior light and cool blue light from outside",
    "dim_closing": "lit dimly, most of the interior lights already off",
}


def character_fragment(fragments: dict[str, str]) -> str:
    return _CHARACTER_TEMPLATE.format(**fragments)


def portrait_prompt(fragments: dict[str, str]) -> str:
    return "\n\n".join([STYLE_BLOCK, character_fragment(fragments), NEGATIVE_BLOCK])


def scene_prompt(scene_id: int) -> str:
    if scene_id not in SCENE_PROMPTS:
        raise ValueError(f"유효하지 않은 장면 번호: {scene_id}")
    return "\n\n".join([STYLE_BLOCK, REFERENCE_SUMMARY, SCENE_PROMPTS[scene_id], NEGATIVE_BLOCK])


def ending_prompt(
    *,
    location: str,
    props: str,
    distance: str,
    camera_shot: str,
    camera_angle: str,
    character_action: str,
    gaze: str,
    composition: str,
    mood: str,
    lighting: str,
) -> str:
    """사실관계 슬롯(location/props/distance)과 연출 슬롯을 합쳐 엔딩 이미지
    프롬프트를 채운다. 둘 다 이미 확정/검증된 값만 들어온다 (CLAUDE.md 5.5)."""
    camera = f"{CAMERA_SHOT_PHRASES[camera_shot]}, {CAMERA_ANGLE_PHRASES[camera_angle]}."
    body = (
        f"{location}. {CHARACTER_ACTION_PHRASES[character_action]}, {GAZE_PHRASES[gaze]}. "
        f"{COMPOSITION_PHRASES[composition]}. {props}. {distance}. "
        f"{MOOD_PHRASES[mood]}, {LIGHTING_PHRASES[lighting]}."
    )
    return "\n\n".join([STYLE_BLOCK_BASE, REFERENCE_SUMMARY, camera, body, NEGATIVE_BLOCK])
