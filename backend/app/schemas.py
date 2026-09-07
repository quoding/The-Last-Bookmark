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
    request_id: str
    presets: PresetSelection


class PortraitRetryRequest(BaseModel):
    request_id: str


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


class EndEarlyResponse(BaseModel):
    status: str


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


class EndingImageRetryResponse(BaseModel):
    image: EndingImageState


class EndingResponse(BaseModel):
    title: str
    body: str
    card: CardState
    evidence: list[EvidenceItem]
    unresolved: list[str]
    image: EndingImageState


class SceneImageEntry(BaseModel):
    id: int
    name: str
    image_url: str | None = None


class SessionStateResponse(BaseModel):
    """GET /api/sessions/{id} — 회차 복원.

    다른 브라우저·기기에서 재진입해도 같은 상태를 그대로 보여주기 위한 필드:
    - portrait_confirmed/presets: 외형만 고르고 "이 모습으로 시작하기"를 누르기
      전에 이탈한 회차인지 구분해 올바른 화면(초상화 확인/대화)으로 보낸다.
    - scenes: 지금까지 지나온 모든 장면의 이미지를 한 번에 돌려줘 완료 회차를
      다른 브라우저에서 열어도 장면 4장을 전부 다시 볼 수 있게 한다.
    """

    id: str
    status: str
    completed_turns: int
    story_time: str
    scene: SceneState
    scenes: list[SceneImageEntry]
    messages: list[MessageOut]
    card_available: bool
    is_final_turn: bool
    portrait: PortraitStatus
    portrait_confirmed: bool
    presets: PresetSelection
