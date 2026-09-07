import hashlib
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  (Base.metadata에 테이블을 등록하기 위해 임포트)
from app.db import Base

TEST_INVITE_CODE = "testcode"
TEST_CODE_ID = "test"


@pytest.fixture(autouse=True)
def _test_settings_env(monkeypatch):
    code_hash = hashlib.sha256(TEST_INVITE_CODE.encode("utf-8")).hexdigest()
    monkeypatch.setenv("INVITE_CODE_HASHES", f"{TEST_CODE_ID}:{code_hash}")
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    monkeypatch.setenv("IMAGE_BUDGET_SESSIONS", "1000")
    # 로컬 개발용 backend/.env가 실제로 존재해도 테스트가 그 값에 흔들리지 않게 고정한다.
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    monkeypatch.setenv("CODE_API_KEYS", "")
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    from app.config import get_settings

    get_settings.cache_clear()

    from app.api import rate_limit

    rate_limit.reset_all()

    yield
    get_settings.cache_clear()
    rate_limit.reset_all()

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://tainai:tainai@localhost:5545/tainai_test"
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db_session(engine):
    """실제 커밋이 일어나는 세션.

    API 테스트는 백그라운드 작업이 별도 커넥션으로 같은 DB에 접근하므로
    트랜잭션-롤백 격리 대신, 매 테스트 뒤 테이블을 TRUNCATE해 격리한다.
    """
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            table_names = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
            conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def fake_image_generator():
    class _FakeGenerator:
        def generate(self, prompt: str):
            return b"fake-generated-bytes", {"text_tokens": 10, "output_tokens": 100}

        def edit(self, prompt: str, reference_image_paths: list[str]):
            return b"fake-edited-bytes", {"text_tokens": 15, "image_tokens": 200, "output_tokens": 100}

    return _FakeGenerator()


class ScriptedLLMClient:
    """LLM 목. 턴별 응답을 큐에 넣어두면 순서대로 소비하고, 없으면 기본 응답을 준다."""

    def __init__(self):
        from app.llm.contracts import EndingParseResult, LLMEndingOutput, LLMTurnOutput, ParseResult

        self._ParseResult = ParseResult
        self._LLMTurnOutput = LLMTurnOutput
        self._EndingParseResult = EndingParseResult
        self._LLMEndingOutput = LLMEndingOutput
        self.turn_queue: list[dict] = []
        self.ending_response: dict | None = None
        self.calls: list[dict] = []

    def generate_turn(self, session, recent_messages, player_input, card=None):
        self.calls.append({"player_input": player_input, "recent_messages": list(recent_messages)})
        if self.turn_queue:
            spec = self.turn_queue.pop(0)
        else:
            spec = {"reply": "알겠어요.", "narration": "", "proposed_events": []}
        output = self._LLMTurnOutput(
            reply=spec.get("reply", "알겠어요."),
            narration=spec.get("narration", ""),
            proposed_events=spec.get("proposed_events", []),
        )
        return self._ParseResult(
            output=output, degraded=False, usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        )

    def generate_ending(self, session, evidence_quotes, card=None):
        spec = self.ending_response or {
            "title": "문을 닫은 뒤에도 남는 말",
            "body": "정리를 마친 서점 안이 조용해졌다. " * 6,
            "unresolved": [],
        }
        output = self._LLMEndingOutput(**spec)
        return self._EndingParseResult(
            output=output, degraded=False, usage={"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}
        )


@pytest.fixture
def fake_llm_client():
    return ScriptedLLMClient()


@pytest.fixture
def client(db_session, fake_image_generator, fake_llm_client, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    from app.config import get_settings

    get_settings.cache_clear()

    import app.db as db_module

    monkeypatch.setattr(db_module, "_engine", None)
    monkeypatch.setattr(db_module, "_SessionLocal", None)

    import app.api.deps as deps_module
    import app.api.sessions as sessions_module
    import app.api.turns as turns_module
    from app.api.deps import get_image_generator
    from app.api.deps_llm import get_llm_client
    from app.db import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    # BackgroundTasks(장면 이미지 생성)는 Depends()를 거치지 않고 build_image_generator를
    # 직접 호출하므로, dependency_overrides만으로는 닿지 않는다. `from ... import`로
    # 각 모듈에 이미 바인딩된 이름까지 전부 바꿔치기한다.
    fake_builder = lambda code_id: fake_image_generator  # noqa: E731
    monkeypatch.setattr(deps_module, "build_image_generator", fake_builder)
    monkeypatch.setattr(sessions_module, "build_image_generator", fake_builder)
    monkeypatch.setattr(turns_module, "build_image_generator", fake_builder)

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_image_generator] = lambda: fake_image_generator
    app.dependency_overrides[get_llm_client] = lambda: fake_llm_client
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_token(client):
    resp = client.post("/api/auth/verify", json={"code": TEST_INVITE_CODE})
    assert resp.status_code == 200
    return resp.json()["token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def make_session(db_session):
    """테스트용 최소 Session 행을 만드는 헬퍼."""
    from app.models import Session as SessionModel

    def _make(**overrides):
        defaults = dict(
            id=uuid.uuid4(),
            code_id="tainai",
            index=1,
            presets={},
        )
        defaults.update(overrides)
        session = SessionModel(**defaults)
        db_session.add(session)
        db_session.flush()
        return session

    return _make
