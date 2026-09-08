"""LLM 응답 스키마와 검증. CLAUDE.md 8.1/8.2.

한 턴에 한 번 호출해 reply/narration/proposed_events를 함께 받는다.
proposed_events는 제안일 뿐이며 engine/state.py가 검증 후 확정한다.
"""

import json

from pydantic import BaseModel, Field, ValidationError


class ProposedEventOut(BaseModel):
    type: str
    payload: dict = Field(default_factory=dict)


class LLMTurnOutput(BaseModel):
    reply: str
    narration: str = ""
    proposed_events: list[ProposedEventOut] = Field(default_factory=list)


class ParseResult(BaseModel):
    output: LLMTurnOutput
    degraded: bool = False  # True면 proposed_events를 못 뽑아 reply만 살렸다는 뜻
    usage: dict | None = None  # {"prompt_tokens", "completion_tokens", "total_tokens"}


class ImageSceneSpecOut(BaseModel):
    """엔딩 이미지 연출 제안. 값은 자유 문자열로 받고, 화이트리스트 검증은
    engine/ending.py에서 한다 — 여기서 Literal로 강제하면 후보 밖 값이
    ValidationError를 일으켜 title/body까지 통째로 강등되기 때문이다.
    """

    location: str = ""
    camera_shot: str = ""
    camera_angle: str = ""
    character_action: str = ""
    gaze: str = ""
    composition: str = ""
    mood: str = ""
    lighting: str = ""


class LLMEndingOutput(BaseModel):
    title: str
    body: str
    unresolved: list[str] = Field(default_factory=list)
    image_scene_spec: ImageSceneSpecOut = Field(default_factory=ImageSceneSpecOut)


class EndingParseResult(BaseModel):
    output: LLMEndingOutput
    degraded: bool = False
    usage: dict | None = None


FALLBACK_ENDING_TITLE = "문을 닫은 뒤에 남은 것"
FALLBACK_ENDING_BODY = (
    "정리를 마친 서점 안이 조용해졌다. 오늘 나눈 말들은 각자의 방식으로 남았다. "
    "문이 닫혀도 그 시간이 사라지는 것은 아니다."
)


def parse_llm_ending_output(raw: str) -> EndingParseResult:
    data = json.loads(raw)
    output = LLMEndingOutput.model_validate(data)
    return EndingParseResult(output=output, degraded=False)


def validate_ending_or_raise(raw: str) -> EndingParseResult:
    try:
        return parse_llm_ending_output(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMOutputError(str(exc)) from exc


def degrade_ending_to_fallback() -> EndingParseResult:
    return EndingParseResult(
        output=LLMEndingOutput(title=FALLBACK_ENDING_TITLE, body=FALLBACK_ENDING_BODY, unresolved=[]),
        degraded=True,
    )


def parse_llm_output(raw: str) -> ParseResult:
    """구조화 출력을 엄격히 검증한다. 실패하면 호출자가 재시도하거나 강등 처리한다."""
    data = json.loads(raw)  # JSONDecodeError는 그대로 위로 던져 재시도를 유도한다
    output = LLMTurnOutput.model_validate(data)
    return ParseResult(output=output, degraded=False)


def degrade_to_reply_only(raw: str) -> ParseResult:
    """엄격 검증이 최종 실패했을 때 대사만이라도 살린다 (CLAUDE.md 8.2 3번).

    JSON에서 reply 필드만 최대한 회수하고, 그마저 없으면 원문 전체를 대사로 쓴다.
    proposed_events는 빈 배열로 처리하고 이 turn은 로깅 대상이 된다.
    """
    reply = raw.strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and isinstance(data.get("reply"), str):
            reply = data["reply"]
    except (json.JSONDecodeError, TypeError):
        pass
    return ParseResult(output=LLMTurnOutput(reply=reply, narration="", proposed_events=[]), degraded=True)


class LLMOutputError(Exception):
    pass


def validate_or_raise(raw: str) -> ParseResult:
    try:
        return parse_llm_output(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMOutputError(str(exc)) from exc
