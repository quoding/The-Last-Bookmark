"""API 응답 스키마.

CLAUDE.md 5.4: trust/closeness/tension 등 내부 수치는 어떤 응답 모델에도
필드로 존재하지 않는다. models.Session에는 그 컬럼들이 있지만 이 파일의
Pydantic 모델은 절대 참조하지 않는다.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AuthVerifyRequest(BaseModel):
    code: str


class AuthVerifyResponse(BaseModel):
    token: str


class SessionListItem(BaseModel):
    id: str
    index: int
    status: str
    completed_turns: int
    ending_title: str | None = None
    portrait_url: str | None = None
    created_at: datetime


class SessionListResponse(BaseModel):
    sessions: list[SessionListItem]


class PresetSelection(BaseModel):
    hair_length: str
    hair_color: str
    bangs: str
    eyes: str
    glasses: str
    impression: str
    build: str


class SessionCreateRequest(BaseModel):
    presets: PresetSelection


class PortraitStatus(BaseModel):
    status: str  # pending / done / failed / refused
    url: str | None = None
    retry_count: int = 0
    retry_limit: int = 2


class SessionCreateResponse(BaseModel):
    id: str
    index: int
    portrait: PortraitStatus


class PortraitRetryResponse(BaseModel):
    portrait: PortraitStatus


class SessionStartResponse(BaseModel):
    id: str
    completed_turns: int
    story_time: str
    scene: "SceneState"


class MessageOut(BaseModel):
    id: str
    turn: int
    kind: str  # player / reply / narration / record
    record_type: str | None = None
    text: str


class SceneState(BaseModel):
    id: int
    name: str
    entered: bool
    image_url: str | None = None


class TurnSubmitRequest(BaseModel):
    request_id: str
    text: str


class TurnResponse(BaseModel):
    messages: list[MessageOut]
    completed_turns: int
    story_time: str
    scene: SceneState
    card_available: bool
    is_final_turn: bool


class CardSubmitRequest(BaseModel):
    request_id: str
    action: str = Field(description="'write' 또는 'leave_blank'")
    text: str | None = None


class CardState(BaseModel):
    written: bool
    text: str | None = None
    author: str | None = None


class EndEarlyRequest(BaseModel):
    request_id: str


class EvidenceItem(BaseModel):
    message_id: str
    turn: int
    story_time: str
    scene_name: str
    quote: str
    effect: str


class EndingImageState(BaseModel):
    status: str  # generating / done / failed / refused
    url: str | None = None


class EndingResponse(BaseModel):
    title: str
    body: str
    card: CardState
    evidence: list[EvidenceItem]
    unresolved: list[str]
    image: EndingImageState


class SessionStateResponse(BaseModel):
    """GET /api/sessions/{id} — 회차 복원."""

    id: str
    status: str
    completed_turns: int
    story_time: str
    scene: SceneState
    messages: list[MessageOut]
    card_available: bool
    is_final_turn: bool
    portrait: PortraitStatus
