"""회차 삭제 검증. story.md/ui-spec.md엔 없던 기능으로 사용자 요청에 따라 추가했다.

images<->sessions 순환 참조를 안전하게 끊고, 이미지 파일도 실제로 지우며,
api_usage_logs는 회차가 지워져도 비용 집계용으로 남아야 한다.
"""

import uuid
from pathlib import Path

from app.images.presets import PRESET_AXES, PRESETS


def _full_preset_selection():
    return {axis: PRESETS[axis][0][0] for axis in PRESET_AXES}


def _create_session(client, auth_headers):
    return client.post(
        "/api/sessions",
        json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()},
        headers=auth_headers,
    )


def test_delete_session_removes_it_from_list(client, auth_headers):
    create_resp = _create_session(client, auth_headers)
    session_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/sessions/{session_id}", headers=auth_headers)
    assert del_resp.status_code == 200
    assert del_resp.json() == {"status": "deleted", "id": session_id}

    listing = client.get("/api/sessions", headers=auth_headers).json()["sessions"]
    assert session_id not in [s["id"] for s in listing]


def test_delete_session_404_after_second_attempt(client, auth_headers):
    create_resp = _create_session(client, auth_headers)
    session_id = create_resp.json()["id"]

    client.delete(f"/api/sessions/{session_id}", headers=auth_headers)
    second = client.delete(f"/api/sessions/{session_id}", headers=auth_headers)
    assert second.status_code == 404


def test_delete_session_requires_ownership(client, auth_headers, monkeypatch):
    import hashlib

    from app.config import get_settings

    create_resp = _create_session(client, auth_headers)
    session_id = create_resp.json()["id"]

    other_code_hash = hashlib.sha256("othercode".encode()).hexdigest()
    monkeypatch.setenv("INVITE_CODE_HASHES", f"test:{hashlib.sha256(b'testcode').hexdigest()},other:{other_code_hash}")
    get_settings.cache_clear()
    try:
        other_token = client.post("/api/auth/verify", json={"code": "othercode"}).json()["token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}

        resp = client.delete(f"/api/sessions/{session_id}", headers=other_headers)
        assert resp.status_code == 404

        # 원래 코드로는 여전히 삭제 가능해야 한다
        still_there = client.get(f"/api/sessions/{session_id}", headers=auth_headers)
        assert still_there.status_code == 200
    finally:
        get_settings.cache_clear()


def test_delete_nonexistent_session_returns_404(client, auth_headers):
    resp = client.delete(f"/api/sessions/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_removes_portrait_image_file_from_disk(client, auth_headers):
    create_resp = _create_session(client, auth_headers)
    body = create_resp.json()
    session_id = body["id"]
    assert body["portrait"]["status"] == "done"

    from app.db import get_sessionmaker
    from app.models import Image, Session as SessionModel

    db = get_sessionmaker()()
    try:
        session_row = db.get(SessionModel, uuid.UUID(session_id))
        image = db.get(Image, session_row.portrait_image_id)
        file_path = Path(image.file_path)
        assert file_path.exists()
    finally:
        db.close()

    client.delete(f"/api/sessions/{session_id}", headers=auth_headers)
    assert not file_path.exists()


def test_delete_session_after_full_flow_keeps_usage_logs(client, auth_headers):
    """엔딩까지 마친 회차를 지워도 api_usage_logs는 남고 session_id만 비워진다."""
    create_resp = _create_session(client, auth_headers)
    session_id = create_resp.json()["id"]
    client.post(f"/api/sessions/{session_id}/start", headers=auth_headers)
    for turn in range(1, 13):
        client.post(
            f"/api/sessions/{session_id}/turns",
            json={"request_id": str(uuid.uuid4()), "text": f"{turn}번째 말"},
            headers=auth_headers,
        )

    from app.db import get_sessionmaker
    from app.models import ApiUsageLog

    db = get_sessionmaker()()
    try:
        before_count = db.query(ApiUsageLog).count()
    finally:
        db.close()
    assert before_count > 0

    del_resp = client.delete(f"/api/sessions/{session_id}", headers=auth_headers)
    assert del_resp.status_code == 200

    db = get_sessionmaker()()
    try:
        after_count = db.query(ApiUsageLog).count()
        orphaned = db.query(ApiUsageLog).filter(ApiUsageLog.session_id.is_(None)).count()
    finally:
        db.close()
    assert after_count == before_count  # 로그 자체는 지워지지 않는다
    assert orphaned >= before_count  # session_id만 비워졌다
