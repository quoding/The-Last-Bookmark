"""프리셋 조합이 항상 같은 영문 프롬프트를 만드는지 검증한다.

번역 호출은 존재하지 않으며, 매핑 상수만으로 결과가 결정되어야 한다.
"""

import itertools

import pytest

from app.images.presets import (
    PRESET_AXES,
    PRESETS,
    InvalidPresetError,
    to_english_fragments,
    to_korean_summary,
    validate_selection,
)
from app.images.prompts import character_fragment, portrait_prompt


def _sample_selection() -> dict[str, str]:
    return {axis: PRESETS[axis][0][0] for axis in PRESET_AXES}


def test_all_axes_present():
    assert set(PRESET_AXES) == {
        "hair_length",
        "hair_color",
        "bangs",
        "eyes",
        "glasses",
        "impression",
        "build",
    }


def test_combination_count_is_5184():
    total = 1
    for axis in PRESET_AXES:
        total *= len(PRESETS[axis])
    assert total == 5184


def test_same_selection_always_produces_same_english_prompt():
    selection = _sample_selection()
    fragments_a = to_english_fragments(selection)
    fragments_b = to_english_fragments(dict(selection))
    prompt_a = portrait_prompt(fragments_a)
    prompt_b = portrait_prompt(fragments_b)
    assert prompt_a == prompt_b


def test_every_combination_is_deterministic_and_valid():
    # 축마다 첫 두 선택지만 뽑아 표본 조합을 검증한다 (전수 5184는 과함).
    sample_axes = {axis: [v[0] for v in PRESETS[axis][:2]] for axis in PRESET_AXES}
    keys = list(sample_axes.keys())
    for combo in itertools.product(*[sample_axes[k] for k in keys]):
        selection = dict(zip(keys, combo))
        fragments = to_english_fragments(selection)
        prompt = character_fragment(fragments)
        assert "{" not in prompt  # 채워지지 않은 슬롯이 없어야 한다
        # 같은 선택은 같은 결과
        assert character_fragment(to_english_fragments(dict(selection))) == prompt


def test_missing_axis_rejected():
    selection = _sample_selection()
    del selection["glasses"]
    with pytest.raises(InvalidPresetError):
        validate_selection(selection)


def test_unknown_value_rejected():
    selection = _sample_selection()
    selection["glasses"] = "sunglasses"
    with pytest.raises(InvalidPresetError):
        validate_selection(selection)


def test_korean_summary_uses_korean_labels_only():
    selection = _sample_selection()
    summary = to_korean_summary(selection)
    for axis in PRESET_AXES:
        english = to_english_fragments(selection)[axis]
        assert english not in summary
