"""이미지 프롬프트 조립과 목 이미지 생성기 인터페이스를 검증한다."""

from app.images import prompts
from app.images.presets import PRESET_AXES, PRESETS, to_english_fragments
from app.images.service import generate_portrait, generate_scene_image


class FakeImageGenerator:
    def __init__(self):
        self.generate_calls: list[str] = []
        self.edit_calls: list[tuple[str, list[str]]] = []

    def generate(self, prompt: str):
        self.generate_calls.append(prompt)
        return b"fake-portrait-bytes", {"text_tokens": 5, "output_tokens": 50}

    def edit(self, prompt: str, reference_image_paths: list[str]):
        self.edit_calls.append((prompt, reference_image_paths))
        return b"fake-scene-bytes", {"text_tokens": 8, "image_tokens": 100, "output_tokens": 50}


def test_scene_prompt_includes_style_and_negative_for_every_scene():
    for scene_id in range(1, 5):
        prompt = prompts.scene_prompt(scene_id)
        assert prompts.STYLE_BLOCK in prompt
        assert prompts.NEGATIVE_BLOCK in prompt
        assert prompts.SCENE_PROMPTS[scene_id] in prompt


def test_scene_prompt_does_not_mention_appearance_axes():
    fragments_pool = [frag for axis in PRESET_AXES for _, _, frag in PRESETS[axis]]
    for scene_id in range(1, 5):
        prompt = prompts.scene_prompt(scene_id)
        for fragment in fragments_pool:
            assert fragment not in prompt


def test_ending_prompt_fills_all_slots():
    prompt = prompts.ending_prompt(
        location="still_at_the_door",
        props="only the keys in hand",
        camera_shot="medium",
        camera_angle="eye_level",
        character_action="turning_back_for_last_look",
        gaze="player",
        composition="centered",
        mood="restrained",
        lighting="dim_closing",
    )
    assert prompts.LOCATION_PHRASES["still_at_the_door"] in prompt
    assert prompts.STYLE_BLOCK_BASE in prompt
    assert prompts.NEGATIVE_BLOCK in prompt
    assert prompts.CAMERA_SHOT_PHRASES["medium"] in prompt


def test_generate_portrait_uses_generate_not_edit(db_session, make_session):
    session = make_session()
    fake = FakeImageGenerator()
    selection = {axis: PRESETS[axis][0][0] for axis in PRESET_AXES}
    fragments = to_english_fragments(selection)
    image = generate_portrait(db_session, fake, session.id, fragments)
    assert len(fake.generate_calls) == 1
    assert len(fake.edit_calls) == 0
    assert image.kind == "portrait"


def test_generate_scene_image_uses_edit_with_reference(db_session, make_session):
    session = make_session()
    fake = FakeImageGenerator()
    image = generate_scene_image(db_session, fake, session.id, 2, "/tmp/portrait.webp")
    assert len(fake.edit_calls) == 1
    prompt, refs = fake.edit_calls[0]
    assert refs == ["/tmp/portrait.webp"]
    assert prompts.SCENE_PROMPTS[2] in prompt
    assert image.scene_id == 2
