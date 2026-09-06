"""SQLAlchemy 모델.

내부 수치(trust/closeness/tension)와 세계 상태는 Session 모델에 컬럼으로
존재하지만, app/schemas.py의 응답 스키마에는 절대 포함하지 않는다.
이 분리가 CLAUDE.md 5.4·8.4의 핵심 규칙이다.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (UniqueConstraint("code_id", "index", name="uq_session_code_index"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    code_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    index: Mapped[int] = mapped_column(Integer, nullable=False)  # 코드별 회차 번호 (1부터)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")
    # in_progress / completed / ended_early

    completed_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    story_time: Mapped[str] = mapped_column(String(5), nullable=False, default="20:30")
    scene_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    presets: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    portrait_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("images.id", use_alter=True, name="fk_sessions_portrait_image_id"),
        nullable=True,
    )
    portrait_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    portrait_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- 내부 수치. API 응답에 절대 노출하지 않는다 (CLAUDE.md 5.4) ---
    trust: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    closeness: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    tension: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # --- 확정 세계 상태 (story.md 8.1) ---
    help_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_offered")
    book_owner: Mapped[str] = mapped_column(String(16), nullable=False, default="seoyun")
    bookmark_owner: Mapped[str] = mapped_column(String(16), nullable=False, default="seoyun")
    future_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    future_plan_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contact_exchanged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    player_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    door_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    ended_early: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    ending_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    ending_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    ending_unresolved: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # list[str]
    ending_evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # list[dict]
    ending_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("images.id", use_alter=True, name="fk_sessions_ending_image_id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["Message"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    card: Mapped["Card | None"] = relationship(back_populates="session", uselist=False, cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # player/reply/narration/record
    record_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # promise/fact/memory
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["Session"] = relationship(back_populates="messages")


class SceneEvent(Base):
    """장면별 고정 사건의 실제 발생 여부와 발생 턴을 기록한다 (story.md 7.1)."""

    __tablename__ = "scene_events"
    __table_args__ = (UniqueConstraint("session_id", "event_key", name="uq_scene_event_once"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    scene_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # 예: opening_started, bookmark_revealed, card_appeared, door_locked
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConfirmedEvent(Base):
    """LLM이 제안한 상태 변화 중 서버가 허용 목록으로 검증해 확정한 것만 남긴다 (CLAUDE.md 5.1)."""

    __tablename__ = "confirmed_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Card(Base):
    """장면 3의 빈 카드. ui-spec.md 7장."""

    __tablename__ = "card"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), unique=True, nullable=False
    )
    written: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(16), nullable=True)  # player/seoyun
    owner: Mapped[str] = mapped_column(String(16), nullable=False, default="seoyun")
    decided_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    session: Mapped["Session"] = relationship(back_populates="card")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # portrait/scene/ending
    scene_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImageJob(Base):
    """CLAUDE.md 9.6의 비동기 상태 테이블. 큐 없이 BackgroundTasks로 처리한다."""

    __tablename__ = "image_jobs"
    __table_args__ = (UniqueConstraint("session_id", "kind", "scene_id", name="uq_image_job_slot"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # portrait/scene/ending
    scene_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    # pending / done / failed / refused
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("images.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RequestLog(Base):
    """request_id 멱등 처리 (CLAUDE.md 5.3). 같은 request_id 재시도는 저장된 응답을 그대로 돌려준다."""

    __tablename__ = "requests"

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
