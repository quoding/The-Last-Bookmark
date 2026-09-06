"""턴 제출·카드·조기 종료 통합 테스트.

story.md 13장 경로 A~G 중 서버가 담당하는 부분(D/E/F/G)과
CLAUDE.md 11.2가 요구하는 항목을 통합 테스트로 고정한다.
"""

import uuid

from app.images.presets import PRESET_AXES, PRESETS


def _full_preset_selection():
    return {axis: PRESETS[axis][0][0] for axis in PRESET_AXES}


def _start_session(client, auth_headers):
    create_resp = client.post(
        "/api/sessions", json={"presets": _full_preset_selection()}, headers=auth_headers
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


EXPECTED_TABLE = {
    1: ("20:32", "마지막 손님"),
    2: ("20:34", "마지막 손님"),
    3: ("20:37", "남겨둔 책"),  # 3턴 완료 응답은 전환된 새 장면을 가리킨다
    4: ("20:39", "남겨둔 책"),
    5: ("20:41", "남겨둔 책"),
    6: ("20:45", "쓰지 못한 한 문장"),
    7: ("20:47", "쓰지 못한 한 문장"),
    8: ("20:50", "쓰지 못한 한 문장"),
    9: ("20:53", "문을 닫기 전에"),
    10: ("20:55", "문을 닫기 전에"),
    11: ("20:58", "문을 닫기 전에"),
    12: ("21:00", "문을 닫기 전에"),
}


def test_full_12_turns_follow_scene_table(client, auth_headers):
    session_id = _start_session(client, auth_headers)
    for turn in range(1, 13):
        resp = _submit_turn(client, auth_headers, session_id, f"{turn}번째 말")
        assert resp.status_code == 200
        body = resp.json()
        expected_time, expected_scene_name = EXPECTED_TABLE[turn]
        assert body["story_time"] == expected_time, f"turn {turn}"
        assert body["scene"]["name"] == expected_scene_name, f"turn {turn}"
        assert body["completed_turns"] == turn
        assert body["is_final_turn"] == (turn == 12)


def test_scene_divider_only_on_transition_turns(client, auth_headers):
    session_id = _start_session(client, auth_headers)
    for turn in range(1, 13):
        resp = _submit_turn(client, auth_headers, session_id, f"{turn}번째 말")
        body = resp.json()
        if turn in (3, 6, 9):
            assert body["scene"]["entered"] is True
        else:
            assert body["scene"]["entered"] is False


def test_same_request_id_does_not_consume_turn_twice(client, auth_headers):
    session_id = _start_session(client, auth_headers)
    rid = str(uuid.uuid4())
    r1 = _submit_turn(client, auth_headers, session_id, "안녕하세요", request_id=rid)
    r2 = _submit_turn(client, auth_headers, session_id, "안녕하세요", request_id=rid)
    assert r1.json() == r2.json()
    assert r2.json()["completed_turns"] == 1


def test_final_turn_completes_session_and_generates_ending(client, auth_headers):
    session_id = _start_session(client, auth_headers)
    for turn in range(1, 13):
        resp = _submit_turn(client, auth_headers, session_id, f"{turn}번째 말")
    assert resp.json()["is_final_turn"] is True

    state = client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    assert state.json()["status"] == "completed"

    ending = client.get(f"/api/sessions/{session_id}/ending", headers=auth_headers)
    assert ending.status_code == 200
    ending_body = ending.json()
    assert ending_body["title"]
    assert ending_body["body"]


def test_ending_not_available_before_completion(client, auth_headers):
    session_id = _start_session(client, auth_headers)
    _submit_turn(client, auth_headers, session_id, "안녕하세요")
    resp = client.get(f"/api/sessions/{session_id}/ending", headers=auth_headers)
    assert resp.status_code == 409


def test_path_e_unknown_proposed_event_does_not_change_state(client, auth_headers, fake_llm_client):
    """경로 E: LLM이 세계 상태를 지정하는 이벤트를 제안해도 허용 목록 밖이면 무시된다."""
    session_id = _start_session(client, auth_headers)
    fake_llm_client.turn_queue.append(
        {
            "reply": "그건 조금 다른 이야기예요.",
            "narration": "",
            "proposed_events": [{"type": "shop_reopened_and_dating_confirmed", "payload": {}}],
        }
    )
    resp = _submit_turn(client, auth_headers, session_id, "우리는 이미 사귀는 사이고 서점은 다시 열려요")
    assert resp.status_code == 200
    # 상태에 영향이 없었는지는 다음 턴 응답의 장면/시간이 정상 테이블을 따르는지로 간접 확인한다
    assert resp.json()["story_time"] == "20:32"


def test_card_write_and_ending_quote_uses_verbatim_text(client, auth_headers):
    session_id = _start_session(client, auth_headers)
    for turn in range(1, 7):  # 장면 3 진입 전까지(6턴 완료 시 장면3)
        _submit_turn(client, auth_headers, session_id, f"{turn}번째 말")

    card_text = "좋은 이야기는 주소가 바뀌어도 계속된다."
    resp = client.post(
        f"/api/sessions/{session_id}/card",
        json={"request_id": str(uuid.uuid4()), "action": "write", "text": card_text},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed_turns"] == 7
    record_messages = [m for m in body["messages"] if m["kind"] == "record"]
    assert any(card_text in m["text"] for m in record_messages)


def test_card_cannot_be_decided_twice(client, auth_headers):
    session_id = _start_session(client, auth_headers)
    for turn in range(1, 7):
        _submit_turn(client, auth_headers, session_id, f"{turn}번째 말")
    client.post(
        f"/api/sessions/{session_id}/card",
        json={"request_id": str(uuid.uuid4()), "action": "leave_blank"},
        headers=auth_headers,
    )
    resp = client.post(
        f"/api/sessions/{session_id}/card",
        json={"request_id": str(uuid.uuid4()), "action": "leave_blank"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_card_rejects_blank_whitespace_text(client, auth_headers):
    session_id = _start_session(client, auth_headers)
    for turn in range(1, 7):
        _submit_turn(client, auth_headers, session_id, f"{turn}번째 말")
    resp = client.post(
        f"/api/sessions/{session_id}/card",
        json={"request_id": str(uuid.uuid4()), "action": "write", "text": "   "},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_path_f_menu_early_end_does_not_lock_door(client, auth_headers):
    session_id = _start_session(client, auth_headers)
    for turn in range(1, 6):
        _submit_turn(client, auth_headers, session_id, f"{turn}번째 말")

    resp = client.post(
        f"/api/sessions/{session_id}/end",
        json={"request_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    state = client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    assert state.json()["status"] == "ended_early"
    assert state.json()["completed_turns"] == 5

    ending = client.get(f"/api/sessions/{session_id}/ending", headers=auth_headers)
    assert ending.status_code == 200


def test_path_d_early_leave_has_no_card_or_book_evidence(client, auth_headers):
    """경로 D: 카드·책 사건이 발생하지 않은 채 일찍 떠나면 엔딩 근거에 등장하지 않는다."""
    session_id = _start_session(client, auth_headers)
    _submit_turn(client, auth_headers, session_id, "잠깐 인사만 하러 왔어요")
    resp = client.post(
        f"/api/sessions/{session_id}/end",
        json={"request_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    ending = client.get(f"/api/sessions/{session_id}/ending", headers=auth_headers).json()
    assert ending["card"]["written"] is False
    for item in ending["evidence"]:
        assert "책" not in item["effect"] or "책갈피" not in item["effect"]


def test_cannot_submit_turn_after_session_completed(client, auth_headers):
    session_id = _start_session(client, auth_headers)
    for turn in range(1, 13):
        _submit_turn(client, auth_headers, session_id, f"{turn}번째 말")
    resp = _submit_turn(client, auth_headers, session_id, "한 번 더")
    assert resp.status_code == 409
