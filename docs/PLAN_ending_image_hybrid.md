# 작업 계획 — 엔딩 이미지 하이브리드 연출 시스템

> 브랜치: `story-v0.4-redesign` (master에서 분기, master는 그대로 안전하게 유지)
> 근거 문서: `ENDING_IMAGE_DIVERSITY_ANALYSIS.md`(추천안 C), `docs/last_bookmark_story_v0.4.md` 9.3~9.5
> 이 문서의 목적: 중간에 대화가 끊기거나 compact되어도 정확히 이 계획으로 이어서 작업할 수 있게 하는 것.
> **작업 순서 3단계 중 1단계.** 2단계(책/책갈피 반환 이벤트 추가), 3단계(opening.py·llm/prompts.py 텍스트를 v0.4로 교체)는 이 작업 완료 후 별도로 진행.

## 목표

엔딩 이미지가 정상 완주 시 사실상 항상 같은 그림(같은 장소·같은 자세·거의 같은 구도)으로 나오는 문제를
"서버=사실관계 확정, LLM=연출(enum) 선택"의 하이브리드 구조로 해결한다.

**원칙(반드시 지킬 것):**
- 서버가 여전히 사실관계(장소, 실제 소유 소품, player 존재 여부, 카드 작성 여부)를 결정한다. LLM은 이 사실을 위반하는 연출을 고를 수 없다.
- LLM은 자유 텍스트가 아니라 **서버가 준 enum 후보 중에서만** 고른다. 화이트리스트 밖 값은 서버가 무시하고 기본값으로 폴백한다.
- DB migration 불필요, `docs/api-contract.md`(API 계약) 불변, frontend(Codex) 수정 불필요 — 전부 `backend/app/` 내부에서 끝낸다.
- 기존 `compute_ending_slots()`의 사실관계 로직(location/props/player_present 판단)은 삭제하지 않고 재사용한다.

## 채택하는 enum 스펙

`docs/last_bookmark_story_v0.4.md` 9.3에 사용자가 이미 정의해둔 값을 그대로 채택한다 (새로 설계하지 않음):

```python
CAMERA_SHOT = ["close", "medium", "full", "wide"]
CAMERA_ANGLE = ["eye_level", "slightly_high", "slightly_low", "side"]
GAZE = ["player", "downward", "away", "object"]
COMPOSITION = ["centered", "left_weighted", "right_weighted", "negative_space"]
MOOD = ["warm", "restrained", "unresolved", "distant", "relieved"]
LIGHTING = ["warm_interior", "blue_rain", "mixed", "dim_closing"]
```

`character_action`은 v0.4 문서가 "현재 상태와 모순되지 않는 행동"이라고만 정하고 구체 목록을 안 줬으므로, 이번 작업에서 아래처럼 **상태 전제조건이 있는 화이트리스트**로 직접 정의한다(문서에 없는 부분이라 구현하면서 확정):

```python
# key: action id, value: (영문 프롬프트 조각, 이 행동이 허용되는 조건 함수)
CHARACTER_ACTIONS = {
    "turning_back_for_last_look":  (항상 허용, 기본값),
    "holding_the_book_close":      book_owner == "seoyun",   # 아직 책을 안 줬을 때만
    "offering_the_card":           card.written == True and card.owner == "seoyun",
    "key_ring_in_hand":            항상 허용 (door_locked는 엔딩 시점엔 늘 True),
    "adjusting_the_apron_pocket":  항상 허용,
    "glancing_toward_departing_player": player_present == False,
    "waving_softly":               player_present == True,
    "hands_empty_at_sides":        book_owner == "player" and bookmark_owner == "player",
}
```

(정확한 최종 목록/영문 문구는 `images/prompts.py` 구현 시점에 SCENE_PROMPTS 톤에 맞춰 다듬는다. 이 표는 뼈대만 고정.)

## 데이터 흐름 (변경 후)

```
_finalize_turn12() (app/api/turns.py)
  → finalize_ending_text() (app/engine/ending.py)
      → generate_ending() LLM 호출 (llm/client.py) — 응답에 title/body/unresolved + image_scene_spec(JSON) 포함
      → validate_image_scene_spec(session, card, raw_spec) (engine/ending.py, 신규 함수)
          - raw_spec의 각 필드가 화이트리스트에 있는지 확인, 없으면 기본값
          - character_action은 상태 전제조건 검사 후 불합격 시 기본값(turning_back_for_last_look)으로 대체
      → compute_ending_slots(session, card) (기존 함수, 그대로 유지) — location/props/player_present 등 "사실관계" 슬롯
      → 두 결과를 병합해 최종 슬롯 딕셔너리 구성
  → background_tasks.add_task(_run_ending_image_job, ..., merged_slots)
  → images/prompts.py: ending_prompt(**merged_slots) — 사실관계 문장 + 연출 문장 조합
  → generator.edit(prompt, [portrait_path])
```

## 파일별 작업 목록

### 1. `backend/app/llm/contracts.py`
- `LLMEndingOutput`에 `image_scene_spec: ImageSceneSpec` 필드 추가 (Pydantic 서브모델).
- `ImageSceneSpec`: `camera_shot`, `camera_angle`, `character_action`, `gaze`, `composition`, `mood`, `lighting` — 전부 `str` (Literal enum으로 걸어도 되고, 문자열로 받고 서버에서 검증해도 됨. Literal을 쓰면 Structured Outputs 스키마 자체가 강제하므로 이쪽을 우선 시도).
- 구조화 출력 실패 시 폴백 로직(`degrade_ending_to_fallback` 류)에도 `image_scene_spec` 기본값 채워 넣기.

### 2. `backend/app/llm/prompts.py`
- `ENDING_RESPONSE_FORMAT_NOTE`(또는 동급 상수)에 `image_scene_spec` JSON 필드와 각 필드의 허용 후보 목록을 명시.
- `build_ending_system_prompt()`에 "다음 사실을 위반하는 연출을 고르면 안 된다"는 안내 추가(예: 책을 이미 줬으면 책을 들고 있는 연출 선택 금지 등, character_action 후보별 조건도 텍스트로 안내).

### 3. `backend/app/engine/ending.py`
- 신규 함수 `validate_image_scene_spec(session, card, raw_spec) -> dict` 추가: enum in-list 체크 + character_action 전제조건 체크, 실패 시 안전한 기본값.
- `finalize_ending_text()`가 이 검증 결과를 함께 반환(또는 세션에 임시 보관 후 다음 단계에 전달)하도록 확장.
- 기존 `compute_ending_slots()`는 그대로 두되, 호출부에서 두 딕셔너리를 병합하는 조합 함수(`build_final_ending_slots` 등) 추가.

### 4. `backend/app/images/prompts.py`
- `ENDING_TEMPLATE`을 확장해 연출 슬롯(camera_shot/camera_angle/character_action/gaze/composition/mood/lighting) 문장을 추가.
- 각 enum 값 → 영문 문구 매핑 사전 추가(`SCENE_PROMPTS`와 같은 방식으로 미리 정의된 조각).
- `STYLE_BLOCK`의 "Vertical composition, full-body framing with headroom"이 모든 이미지(초상화/장면/엔딩) 공통 고정 문구인데, 엔딩만 camera_shot(close/medium/full/wide)을 다양화하려면 이 문구가 충돌한다. **엔딩 전용 스타일 조각을 분리**하거나, STYLE_BLOCK에서 구도 지시 부분만 빼고 엔딩 프롬프트 조립 시 별도로 camera_shot 문구를 추가하는 방식으로 처리(세로 이미지 비율 자체는 유지, 그 안에서의 프레이밍만 조정).

### 5. `backend/app/api/turns.py`, `backend/app/api/ending.py`
- `_finalize_turn12`와 엔딩 이미지 재시도 경로(`retry_ending_image` 등)가 새 병합 함수를 호출하도록 배선 변경.

## 테스트 계획

- LLM/이미지 호출은 전부 목(mock)으로 대체(기존 테스트 스타일 그대로).
- 신규 테스트:
  - `image_scene_spec`이 화이트리스트 밖 값을 낼 때 기본값으로 폴백되는지.
  - `character_action` 전제조건 위반 시(예: book_owner=="player"인데 `holding_the_book_close` 선택) 거부되고 기본값으로 대체되는지.
  - 기존 `compute_ending_slots()` 기반 사실관계 슬롯(location/props/player_present)이 그대로 최종 프롬프트에 포함되는지.
  - 구조화 출력 실패 시 폴백 경로에서도 이미지 생성이 죽지 않는지(기본 연출값으로 정상 진행).
- **실제 OpenAI API로 이미지 생성 테스트는 사용자가 직접 한다** (지난 피드백: Claude는 테스트 중 실제 이미지 생성 API를 호출하지 않는다). 목 테스트로 프롬프트 조립 결과 문자열까지만 검증하고, 실제 그림이 다양해지는지는 사용자가 실제 플레이로 확인.

## 진행 체크리스트

- [ ] 1. `llm/contracts.py` — `ImageSceneSpec` 스키마 추가
- [ ] 2. `llm/prompts.py` — 엔딩 시스템 프롬프트에 연출 필드 스펙/제약 안내 추가
- [ ] 3. `engine/ending.py` — 검증 함수 + 병합 함수 추가
- [ ] 4. `images/prompts.py` — 연출 슬롯 문구 매핑 + ENDING_TEMPLATE 확장 + STYLE_BLOCK 구도 문구 분리
- [ ] 5. `api/turns.py`, `api/ending.py` — 호출부 배선 변경
- [ ] 6. 신규 테스트 작성, 전체 테스트 스위트 통과 확인
- [ ] 7. 사용자에게 실제 플레이 테스트 요청(이미지 다양성 체감 확인)
- [ ] 8. 완료 후 `story-v0.4-redesign` 브랜치에 커밋

이 체크리스트를 진행하면서 완료된 항목은 이 파일에서 `[x]`로 갱신한다.
