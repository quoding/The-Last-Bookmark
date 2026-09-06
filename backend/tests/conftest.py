import hashlib
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db import Base

TEST_INVITE_CODE = "testcode"
TEST_CODE_ID = "test"


@pytest.fixture(autouse=True)
def _test_settings_env(monkeypatch):
    code_hash = hashlib.sha256(TEST_INVITE_CODE.encode("utf-8")).hexdigest()
    monkeypatch.setenv("INVITE_CODE_HASHES", f"{TEST_CODE_ID}:{code_hash}")
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    monkeypatch.setenv("IMAGE_BUDGET_SESSIONS", "1000")
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

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
        def generate(self, prompt: str) -> bytes:
            return b"fake-generated-bytes"

        def edit(self, prompt: str, reference_image_paths: list[str]) -> bytes:
            return b"fake-edited-bytes"

    return _FakeGenerator()


@pytest.fixture
def client(db_session, fake_image_generator, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    from app.config import get_settings

    get_settings.cache_clear()

    import app.db as db_module

    monkeypatch.setattr(db_module, "_engine", None)
    monkeypatch.setattr(db_module, "_SessionLocal", None)

    from app.api.deps import get_image_generator
    from app.db import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_image_generator] = lambda: fake_image_generator
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
