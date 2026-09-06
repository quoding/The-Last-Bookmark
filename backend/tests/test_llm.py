"""LLM 계약 검증과 재시도 동작. 실제 API 호출은 목으로 대체한다."""

import json
import uuid

import pytest

from app.llm.client import MAX_RETRIES, OpenAILLMClient
from app.llm.contracts import LLMOutputError, degrade_to_reply_only, parse_llm_output, validate_or_raise
from app.llm.prompts import FORBIDDEN_NOTES, build_messages, confirmed_state_summary
from app.models import Session


def _fresh_session(**overrides) -> Session:
    defaults = dict(
        id=uuid.uuid4(),
        code_id="test",
        index=1,
        presets={},
        scene_id=1,
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


VALID_JSON = json.dumps(
    {
        "reply": "오늘은 책 사러 오셨다고 해도 못 팔아요.",
        "narration": "서윤이 웃으며 상자를 발끝으로 밀어둔다.",
        "proposed_events": [{"type": "help_offered", "payload": {}}],
    },
    ensure_ascii=False,
)


def test_parse_valid_json():
    result = parse_llm_output(VALID_JSON)
    assert result.output.reply.startswith("오늘은")
    assert result.output.proposed_events[0].type == "help_offered"
    assert result.degraded is False


def test_parse_rejects_missing_reply():
    with pytest.raises(LLMOutputError):
        validate_or_raise(json.dumps({"narration": "설명만 있음"}))


def test_parse_rejects_non_json():
    with pytest.raises(LLMOutputError):
        validate_or_raise("이건 그냥 텍스트입니다")


def test_degrade_recovers_reply_from_partial_json():
    raw = '{"reply": "그래도 대사는 있어요", "proposed_events": [invalid'
    result = degrade_to_reply_only(raw)
    assert result.degraded is True
    assert result.output.proposed_events == []
    assert result.output.reply  # 비어있지 않다


def test_degrade_falls_back_to_raw_text_when_totally_unparseable():
    result = degrade_to_reply_only("그냥 순수 텍스트 응답")
    assert result.output.reply == "그냥 순수 텍스트 응답"
    assert result.degraded is True


def test_prompt_includes_appearance_prohibition():
    session = _fresh_session()
    messages = build_messages(session, [], "안녕하세요")
    system_content = messages[0]["content"]
    assert any("외형" in note for note in FORBIDDEN_NOTES)
    assert "외형" in system_content


def test_prompt_confirmed_state_reflects_book_owner():
    session = _fresh_session(book_owner="player")
    summary = confirmed_state_summary(session)
    assert "플레이어" in summary


class _ScriptedClient(OpenAILLMClient):
    def __init__(self, script: list[str]):
        self._script = list(script)
        self._calls = 0

    def _call_once(self, messages: list[dict]) -> str:
        self._calls += 1
        return self._script.pop(0)


def test_retries_on_invalid_json_then_succeeds():
    client = _ScriptedClient(["망가진 응답", VALID_JSON])
    session = _fresh_session()
    result = client.generate_turn(session, [], "안녕하세요")
    assert result.degraded is False
    assert client._calls == 2


def test_gives_up_after_max_retries_and_keeps_reply_only():
    script = ["broken"] * (MAX_RETRIES + 1)
    client = _ScriptedClient(script)
    session = _fresh_session()
    result = client.generate_turn(session, [], "안녕하세요")
    assert result.degraded is True
    assert result.output.proposed_events == []
    assert client._calls == MAX_RETRIES + 1
