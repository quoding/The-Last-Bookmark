"""LLM 호출. CLAUDE.md 8.1~8.2.

1턴 = 1회 호출. 구조화 출력을 우선 시도하고, 실패하면 최대 2회 재시도
(턴을 소비하지 않는다). 그래도 실패하면 reply만 살리고 proposed_events는
빈 배열로 처리한 뒤 로깅한다. 대사가 나오는 것이 사건 추출보다 우선이다.
"""

import logging
from typing import Protocol

from app.config import get_settings
from app.llm.contracts import (
    EndingParseResult,
    LLMOutputError,
    ParseResult,
    degrade_ending_to_fallback,
    degrade_to_reply_only,
    validate_ending_or_raise,
    validate_or_raise,
)
from app.llm.prompts import build_ending_messages, build_messages
from app.models import Session

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


class LLMClient(Protocol):
    def generate_turn(
        self, session: Session, recent_messages: list, player_input: str, card=None
    ) -> ParseResult: ...

    def generate_ending(self, session: Session, evidence_quotes: list[str], card=None) -> EndingParseResult: ...


class OpenAILLMClient:
    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self._model = settings.llm_model
        self._api_key = api_key or settings.llm_api_key

    def _client(self):
        from openai import OpenAI

        return OpenAI(api_key=self._api_key)

    def _call_once(self, messages: list[dict]) -> tuple[str, dict | None]:
        client = self._client()
        response = client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        usage = None
        if response.usage is not None:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        return response.choices[0].message.content or "", usage

    def generate_turn(
        self, session: Session, recent_messages: list, player_input: str, card=None
    ) -> ParseResult:
        messages = build_messages(session, recent_messages, player_input, card)

        last_raw = ""
        last_usage: dict | None = None
        for attempt in range(MAX_RETRIES + 1):
            raw, usage = self._call_once(messages)
            last_raw, last_usage = raw, usage
            try:
                result = validate_or_raise(raw)
                result.usage = usage
                return result
            except LLMOutputError as exc:
                logger.warning("LLM 구조화 출력 검증 실패 (시도 %d/%d): %s", attempt + 1, MAX_RETRIES + 1, exc)

        logger.error("LLM 구조화 출력이 %d회 재시도 후에도 실패해 대사만 살립니다.", MAX_RETRIES + 1)
        result = degrade_to_reply_only(last_raw)
        result.usage = last_usage
        return result

    def generate_ending(self, session: Session, evidence_quotes: list[str], card=None) -> EndingParseResult:
        messages = build_ending_messages(session, evidence_quotes, card)
        last_usage: dict | None = None
        for attempt in range(MAX_RETRIES + 1):
            raw, usage = self._call_once(messages)
            last_usage = usage
            try:
                result = validate_ending_or_raise(raw)
                result.usage = usage
                return result
            except LLMOutputError as exc:
                logger.warning(
                    "엔딩 LLM 출력 검증 실패 (시도 %d/%d): %s", attempt + 1, MAX_RETRIES + 1, exc
                )
        logger.error("엔딩 생성이 %d회 재시도 후에도 실패해 대체 문구를 사용합니다.", MAX_RETRIES + 1)
        result = degrade_ending_to_fallback()
        result.usage = last_usage
        return result
