"""엔딩 근거 선택과 기타 CLAUDE.md 11.2 항목을 보강한다."""

import uuid

from app.images.presets import PRESET_AXES, PRESETS


def _full_preset_selection():
    return {axis: PRESETS[axis][0][0] for axis in PRESET_AXES}


def _start_session(client, auth_headers):
    create_resp = client.post(
        "/api/sessions", json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()}, headers=auth_headers
    )
    session_id = create_resp.json()["id"]
    client.post(f"/api/sessions/{session_id}/start", headers=auth_headers)
    return session_id


def _submit_turn(client, auth_headers, session_id, text, request_id=None):
    return client.post(
        f"/api/sessions/{session_id}/turns",
        json={"request_id": request_id or str(uuid.uuid4()), "text": text},
        headers=auth_headers,
    )


def test_personal_detail_shared_becomes_ending_evidence(client, auth_headers, fake_llm_client):
    """책/카드 같은 정해진 사건과 무관한 개인적인 대화도 근거로 남아야 한다."""
    session_id = _start_session(client, auth_headers)
    fake_llm_client.turn_queue.append(
        {
            "reply": "그런 이유로 오늘 들르셨군요.",
            "narration": "",
            "proposed_events": [{"type": "personal_detail_shared", "payload": {}}],
        }
    )
    _submit_turn(client, auth_headers, session_id, "요즘 이직 준비 중이라 마음이 복잡해서 왔어요")

    resp = client.post(
        f"/api/sessions/{session_id}/end",
        json={"request_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    ending = client.get(f"/api/sessions/{session_id}/ending", headers=auth_headers).json()
    quotes = [e["quote"] for e in ending["evidence"]]
    assert "요즘 이직 준비 중이라 마음이 복잡해서 왔어요" in quotes


def test_proposal_without_acceptance_is_not_evidence(client, auth_headers, fake_llm_client):
    """경로 B: 제안과 수락을 구분한다. 제안만 있으면 근거로 회수되지 않는다."""
    session_id = _start_session(client, auth_headers)
    fake_llm_client.turn_queue.append(
        {
            "reply": "다음에 또 봐요.",
            "narration": "",
            "proposed_events": [{"type": "future_plan_proposed", "payload": {"text": "또 오기"}}],
        }
    )
    _submit_turn(client, auth_headers, session_id, "다음에 또 올게요")

    resp = client.post(
        f"/api/sessions/{session_id}/end",
        json={"request_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    ending = client.get(f"/api/sessions/{session_id}/ending", headers=auth_headers).json()
    effects = [e["effect"] for e in ending["evidence"]]
    assert not any("약속" in effect for effect in effects)


def test_acceptance_after_proposal_becomes_evidence(client, auth_headers, fake_llm_client):
    session_id = _start_session(client, auth_headers)
    fake_llm_client.turn_queue.append(
        {
            "reply": "다음에 또 봐요.",
            "narration": "",
            "proposed_events": [{"type": "future_plan_proposed", "payload": {"text": "또 오기"}}],
        }
    )
    _submit_turn(client, auth_headers, session_id, "다음에 또 올게요")

    fake_llm_client.turn_queue.append(
        {
            "reply": "좋아요, 그럼 그때 봐요.",
            "narration": "",
            "proposed_events": [{"type": "future_plan_accepted", "payload": {}}],
        }
    )
    _submit_turn(client, auth_headers, session_id, "꼭 그렇게 해요")

    resp = client.post(
        f"/api/sessions/{session_id}/end",
        json={"request_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    ending = client.get(f"/api/sessions/{session_id}/ending", headers=auth_headers).json()
    effects = [e["effect"] for e in ending["evidence"]]
    assert any("약속" in effect for effect in effects)


def test_book_returned_after_given_becomes_evidence(client, auth_headers, fake_llm_client):
    """책을 받았다가 다시 돌려주는 것도 확정 사건으로 기록되고 엔딩 근거로 회수된다."""
    session_id = _start_session(client, auth_headers)
    for turn in range(1, 4):  # scene_id>=2 조건을 만족시키려고 장면 전환까지 진행
        _submit_turn(client, auth_headers, session_id, f"{turn}번째 말")

    fake_llm_client.turn_queue.append(
        {
            "reply": "이 책, 가져가세요.",
            "narration": "",
            "proposed_events": [{"type": "book_given", "payload": {}}],
        }
    )
    _submit_turn(client, auth_headers, session_id, "그 책 저 주시는 거예요?")

    fake_llm_client.turn_queue.append(
        {
            "reply": "그럼 다시 받아둘게요.",
            "narration": "",
            "proposed_events": [{"type": "book_returned", "payload": {}}],
        }
    )
    _submit_turn(client, auth_headers, session_id, "생각해보니 이건 서윤씨가 갖고 있어야 할 것 같아요")

    resp = client.post(
        f"/api/sessions/{session_id}/end",
        json={"request_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    ending = client.get(f"/api/sessions/{session_id}/ending", headers=auth_headers).json()
    effects = [e["effect"] for e in ending["evidence"]]
    assert any("돌려주는" in effect for effect in effects)


def test_same_turn_confirming_two_events_does_not_duplicate_evidence_quote(
    client, auth_headers, fake_llm_client
):
    """실사고: 같은 턴에 book_given과 bookmark_given이 함께 확정되면 같은 원문이
    근거 목록에 두 번 뜨는 버그가 있었다. 이제는 한 번만 뜨고 효과 문장만 합쳐진다."""
    session_id = _start_session(client, auth_headers)
    for turn in range(1, 4):
        _submit_turn(client, auth_headers, session_id, f"{turn}번째 말")

    fake_llm_client.turn_queue.append(
        {
            "reply": "책이랑 책갈피 같이 드릴게요.",
            "narration": "",
            "proposed_events": [
                {"type": "book_given", "payload": {}},
                {"type": "bookmark_given", "payload": {}},
            ],
        }
    )
    _submit_turn(client, auth_headers, session_id, "감사해요 잘 읽을게요")

    resp = client.post(
        f"/api/sessions/{session_id}/end",
        json={"request_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    ending = client.get(f"/api/sessions/{session_id}/ending", headers=auth_headers).json()
    quotes = [e["quote"] for e in ending["evidence"]]
    assert quotes.count("감사해요 잘 읽을게요") == 1
    matching = [e for e in ending["evidence"] if e["quote"] == "감사해요 잘 읽을게요"][0]
    assert "책" in matching["effect"] and "책갈피" in matching["effect"]


def test_image_budget_blocks_new_session(client, auth_headers, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("IMAGE_BUDGET_SESSIONS", "1")
    get_settings.cache_clear()
    try:
        first = client.post(
            "/api/sessions", json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()}, headers=auth_headers
        )
        assert first.status_code == 200

        second = client.post(
            "/api/sessions", json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()}, headers=auth_headers
        )
        assert second.status_code == 403
    finally:
        get_settings.cache_clear()


def test_portrait_retry_after_failure_does_not_consume_quota(client, auth_headers, fake_image_generator, monkeypatch):
    create_resp = client.post(
        "/api/sessions", json={"request_id": str(uuid.uuid4()), "presets": _full_preset_selection()}, headers=auth_headers
    )
    session_id = create_resp.json()["id"]

    call_count = {"n": 0}
    original_generate = fake_image_generator.generate

    def _failing_generate(prompt):
        call_count["n"] += 1
        raise RuntimeError("이미지 생성 실패(테스트)")

    monkeypatch.setattr(fake_image_generator, "generate", _failing_generate)
    r1 = client.post(
        f"/api/sessions/{session_id}/portrait/retry",
        json={"request_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert r1.json()["portrait"]["status"] == "failed"
    assert r1.json()["portrait"]["retry_count"] == 1  # 성공한 초상화를 스스로 다시 그리려던 시도라 횟수를 쓴다

    # 방금 실패했으니 그 실패를 만회하려는 재시도는 남은 횟수를 쓰지 않는다
    monkeypatch.setattr(fake_image_generator, "generate", original_generate)
    r2 = client.post(
        f"/api/sessions/{session_id}/portrait/retry",
        json={"request_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert r2.json()["portrait"]["status"] == "done"
    assert r2.json()["portrait"]["retry_count"] == 1


def test_completed_session_appears_in_list_with_ending_title(client, auth_headers):
    session_id = _start_session(client, auth_headers)
    for turn in range(1, 13):
        _submit_turn(client, auth_headers, session_id, f"{turn}번째 말")

    listing = client.get("/api/sessions", headers=auth_headers).json()["sessions"]
    entry = next(s for s in listing if s["id"] == session_id)
    assert entry["status"] == "completed"
    assert entry["ending_title"]
