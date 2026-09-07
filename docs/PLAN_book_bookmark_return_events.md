# 작업 계획 — 책/책갈피 "돌려준다" 이벤트 추가

> 브랜치: `story-v0.4-redesign`
> 근거: `docs/last_bookmark_story_v0.4.md` 6.2 "책/책갈피 선택 — 받는다 / 거절한다 / 돌려준다 / 의미를
> 묻는다 모두 가능"인데, 현재 `backend/app/engine/state.py`의 이벤트 화이트리스트에는
> `book_given`/`book_declined`/`bookmark_given`만 있고 "돌려준다"(한 번 받았다가 다시 돌려주는 것)에
> 해당하는 이벤트가 없다. **3단계 계획 중 2단계.** (1단계: 엔딩 이미지 하이브리드, 완료.
> 3단계: opening.py·llm/prompts.py를 v0.4 내용으로 교체, 아직 시작 안 함.)

## 목표

- `book_returned`: 플레이어가 이미 받은 책을 다시 서윤에게 돌려주는 이벤트. `book_owner`가
  `"player"`일 때만 성립하며, 성공하면 `book_owner`를 다시 `"seoyun"`으로 되돌린다.
- `bookmark_returned`: 위와 동일하되 책갈피 대상.
- `bookmark_declined`: 현재 `book_declined`(상태 변화 없이 그냥 거절 기록만 남김, 대신 어떤
  다른 것도 안 바꿈)와 대칭을 맞추기 위해 추가. `bookmark_given`이 아직 안 됐을 때만 성립.

이 세 이벤트를 `engine/state.py`의 `APPLIERS`/`RECORD_TEMPLATES`에 추가하고,
`llm/prompts.py`의 `ALLOWED_EVENT_TYPES`(LLM이 제안할 수 있는 이벤트 목록)에도 추가한다.
`engine/ending.py`의 `EVIDENCE_EFFECT_TEXT`에도 "돌려줌"이 엔딩 근거로 회수될 수 있게 추가한다.

## 설계

```python
# engine/state.py APPLIERS에 추가
def _apply_book_returned(session, payload):
    if session.book_owner == "player":
        session.book_owner = "seoyun"
        return True
    return False

def _apply_bookmark_returned(session, payload):
    if session.bookmark_owner == "player":
        session.bookmark_owner = "seoyun"
        return True
    return False

def _apply_bookmark_declined(session, payload):
    return session.scene_id >= 2 and session.bookmark_owner == "seoyun"
```

`RECORD_TEMPLATES` 추가:
- `book_returned`: `("memory", "결국 책을 다시 서윤에게 돌려주었다")`
- `bookmark_returned`: `("memory", "책갈피를 다시 서윤의 손에 돌려주었다")`
- `bookmark_declined`: `(None, None)` (book_declined과 동일하게 시스템 기록 카드는 안 만듦)

`engine/ending.py`의 `EVIDENCE_EFFECT_TEXT`에 추가(엔딩 근거로 회수 가능하게):
- `book_returned`: `"이 말이 책을 다시 돌려주는 결정으로 이어졌다."`
- `bookmark_returned`: `"이 말이 책갈피를 다시 돌려주는 결정으로 이어졌다."`

## 영향 범위

- DB migration 불필요 (기존 컬럼 재사용, 새 컬럼 없음).
- API 계약 불변 (내부 상태 전이 로직일 뿐 응답 스키마 변화 없음).
- frontend(Codex) 수정 불필요.
- 수정 파일: `backend/app/engine/state.py`, `backend/app/llm/prompts.py`(ALLOWED_EVENT_TYPES),
  `backend/app/engine/ending.py`(EVIDENCE_EFFECT_TEXT).

## 테스트 계획

- `book_returned`가 `book_owner=="seoyun"`일 때(아직 안 받음) 무시되는지.
- `book_returned`가 `book_owner=="player"`일 때 성공하고 `book_owner`가 다시 `"seoyun"`이
  되는지, 이후 `book_given`을 다시 제안하면 성립하는지(왕복 가능한지).
- `bookmark_returned` 동일 패턴.
- `bookmark_declined`가 `bookmark_owner=="seoyun"`일 때만 성립하는지.
- 엔딩 근거(evidence)에 `book_returned`/`bookmark_returned`가 잡히는지.

## 체크리스트

- [x] 1. `engine/state.py` — 3개 이벤트 appliers + RECORD_TEMPLATES 추가
- [x] 2. `llm/prompts.py` — `ALLOWED_EVENT_TYPES`에 3개 추가
- [x] 3. `engine/ending.py` — `EVIDENCE_EFFECT_TEXT`에 2개 추가
- [x] 4. 신규 테스트 작성(`test_state_engine.py` 7개 + `test_ending_evidence_and_misc.py` 1개), 전체 스위트 138개 통과 확인
- [x] 5. `story-v0.4-redesign` 브랜치에 커밋

**완료.** 다음은 3단계(opening.py·llm/prompts.py를 v0.4 스토리 내용으로 교체)로 진행.
