"""LLM·이미지 호출의 실제 토큰 사용량을 코드별로 기록한다.

비용(원화·달러) 계산은 여기서 하지 않는다. 단가는 관리자 페이지에서
조회 시점에 입력·수정할 수 있게 하고, 여기서는 원시 토큰 수만 남긴다.
"""

import uuid

from sqlalchemy.orm import Session as DbSession

from app.images.openai_images import ImageUsage
from app.models import ApiUsageLog


def log_image_usage(
    db: DbSession,
    code_id: str,
    session_id: uuid.UUID | None,
    model: str,
    usage: ImageUsage | None,
) -> None:
    if usage is None:
        return
    db.add(
        ApiUsageLog(
            code_id=code_id,
            session_id=session_id,
            kind="image",
            model=model,
            text_tokens=usage.get("text_tokens", 0),
            image_tokens=usage.get("image_tokens", 0),
            cached_text_tokens=usage.get("cached_text_tokens", 0),
            cached_image_tokens=usage.get("cached_image_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
    )


def log_llm_usage(
    db: DbSession,
    code_id: str,
    session_id: uuid.UUID | None,
    model: str,
    usage: dict | None,
) -> None:
    if usage is None:
        return
    db.add(
        ApiUsageLog(
            code_id=code_id,
            session_id=session_id,
            kind="llm",
            model=model,
            text_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )
    )
