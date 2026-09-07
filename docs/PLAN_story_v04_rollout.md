# 작업 계획 — 스토리 v0.4 실제 반영 (3단계, 마지막)

> 브랜치: `story-v0.4-redesign`
> 근거: `docs/last_bookmark_story_v0.4.md`
> 1단계(엔딩 이미지 하이브리드), 2단계(책/책갈피 반환 이벤트) 완료. 이 문서는 마지막 3단계.

## 목표

지금까지 v0.4는 문서로만 존재했고 실제 게임(LLM 프롬프트, 오프닝 대사)은 여전히 구버전
story.md(v0.3) 내용으로 동작했다. 이번 작업으로 실제 대사·페르소나가 v0.4 내용을 쓰도록 만든다.

## 바꾸는 파일과 내용

1. **`backend/app/llm/prompts.py`**
   - `PERSONA_YAML`: v0.4 12장의 `character:` YAML 블록으로 교체(겉/내적 성향, 현재 욕구/숨은 욕구,
     관계상의 어려움, 중요 가치 등 더 깊어진 설정 반영).
   - `SCENARIO_YAML`: v0.4 12장의 `scenario:` YAML 블록으로 교체(`scene_functions`,
     새 `fixed_beats` 4개, `version: 0.4`).
   - `SCENE_BRIEFS`: 4개 장면 각각 v0.4 6.1~6.4의 장면명·목적·공간·고정 사건·턴 기능으로 재작성.
     장면 이름이 바뀐다: "마지막 손님"→"남겨진 것", "남겨둔 책"→"조금 늦은 안부",
     "쓰지 못한 한 문장"(유지), "문을 닫기 전에"→"21:00".
   - `FORBIDDEN_NOTES`: 기존 항목은 대부분 그대로 유효(외형 언급 금지, 세계상태 미확정 등
     캐릭터 불문 공통 규칙). 카드가 "특정 인물에게 보내려던 편지가 아님"을 임의로 먼저 확정하지
     않는다는 주의만 한 줄 추가.
   - `GUIDANCE_NOTES`: 기존 항목 유지(여지 남기기 지침, 방금 고침). v0.4의 "장면 종료 시 질문"
     개념을 SCENE_BRIEFS에 녹여 중복 추가하지 않는다.

2. **`backend/app/engine/opening.py`**
   - v0.4 6.1의 "첫 화면 설명"·"시작 대사"로 교체. 책과 빈 카드가 아직 안 치워졌다는 사실을
     오프닝 내레이션에 명시(v0.4의 Scene 1 필수 공개 사항).

3. **`docs/story.md`**
   - v0.4 내용으로 교체(버전 문자열도 v0.4로). `docs/last_bookmark_story_v0.4.md`는 이제 중복
     초안이므로 삭제하고, `docs/story.md` 하나만 정본으로 유지한다(CLAUDE.md 0장이 참조하는
     구조와 일치시키기 위함 — 두 스토리 문서가 동시에 존재하면 나중에 또 헷갈린다).

## 이번 작업에서 하지 않는 것

- 장면 이미지 프롬프트(`images/prompts.py`의 `SCENE_PROMPTS`)는 그대로 둔다 — v0.4의 장면
  공간 묘사가 기존 이미지 프롬프트와 이미 거의 1:1로 일치해서(서가 통로/카운터/창가 탁자/
  처마) 이미지 쪽은 손댈 필요가 없다(`STORY_REDESIGN_CONSTRAINTS.md`에서 이미 확인함).
- 장면 전환 로직(턴→장면 매핑)이나 카드 게이트(scene_id>=3) 같은 코드 구조는 전혀 안 바꾼다.
  v0.4도 이 구조를 그대로 쓰기로 설계됐다.

## 영향 범위

- DB migration 불필요, API 계약 불변, frontend 수정 불필요(순수 텍스트/설정 콘텐츠 변경).
- 기존 테스트 중 특정 장면 이름 문자열을 assert하는 테스트가 있으면 이름이 바뀌므로 같이
  고쳐야 한다(`tests/test_turns_and_card.py`의 `EXPECTED_TABLE` 등).

## 체크리스트

- [x] 1. `llm/prompts.py` — PERSONA_YAML/SCENARIO_YAML/SCENE_BRIEFS 교체(+FORBIDDEN_NOTES 카드 오해 방지 1줄 추가)
- [x] 2. `engine/opening.py` — 오프닝 텍스트 교체(책+빈 카드 존재 공개 포함)
- [x] 3. `docs/story.md` 교체, `docs/last_bookmark_story_v0.4.md` 삭제. `docs/api-contract.md`·
      `docs/ui-spec.md`의 예시 장면 이름도 새 이름으로 갱신(계약 형태 변화 없음, 값만 갱신)
- [x] 4. 장면 이름 문자열을 assert하던 기존 테스트 갱신(`test_scene_engine.py`,
      `test_contract_extensions.py`, `test_turns_and_card.py`) — sed로 일괄 치환, 수정 불필요했음
- [x] 5. 전체 테스트 스위트 138개 통과 확인
- [x] 6. `story-v0.4-redesign` 브랜치에 커밋
- [ ] 7. 사용자에게 실제 플레이 검증 요청, 이상 없으면 `master`에 merge하고 재배포

## 장면 이름 변경 (실제 반영됨)

| 장면 | 이전(v0.3) | 이후(v0.4) |
|---|---|---|
| 1 | 마지막 손님 | 남겨진 것 |
| 2 | 남겨둔 책 | 조금 늦은 안부 |
| 3 | 쓰지 못한 한 문장 | (동일) |
| 4 | 문을 닫기 전에 | 21:00 |

`GET /api/sessions/{id}`·턴 응답의 `scene.name`, 엔딩 evidence의 `scene_name` 필드 값이 이제
새 이름으로 나간다. API 계약의 필드 형태(shape)는 그대로라 `docs/api-contract.md` 스키마 변경은
아니지만, 프론트가 장면 이름을 화면에 그대로 표시하므로(ui-spec.md 5.1 구분선 등) **화면에 보이는
텍스트가 바뀐다는 것을 Codex에게 알려줘야 한다** — 코드 수정은 필요 없고 그냥 참고 사항.
