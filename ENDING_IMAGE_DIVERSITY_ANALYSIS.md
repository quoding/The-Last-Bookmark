# 엔딩 이미지 다양성 분석

> 조사 전용 문서. 코드는 수정하지 않았다. 모든 근거는 실제 코드(2026-09-08 기준)를 직접 읽어 확인했다.

## 1. 현재 엔딩 이미지 생성 구조

데이터 흐름 (파일/함수 포함):

```
플레이어 대화 (POST /api/sessions/{id}/turns, app/api/turns.py:submit_turn)
  → LLM turn 호출 (app/llm/client.py:OpenAILLMClient.generate_turn)
  → proposed_events (app/llm/contracts.py:LLMTurnOutput.proposed_events)
  → 서버 확정 (app/engine/state.py:confirm_proposed_events) → ConfirmedEvent 행 + Session 컬럼 갱신
      (help_status/book_owner/bookmark_owner/future_plan*/contact_exchanged/player_present)
  → 턴 12 도달 시 _finalize_turn12() (app/api/turns.py:81)
      1) session.door_locked = True (무조건, 조건 없음)
      2) finalize_ending_text() (app/engine/ending.py:116) → 엔딩 LLM 호출로 title/body/unresolved 확정
      3) compute_ending_slots(session, card) (app/engine/ending.py:84) → location/posture/expression/props/distance 5개 슬롯 결정
      4) background_tasks.add_task(_run_ending_image_job, ...) (app/api/turns.py:46)
  → _run_ending_image_job → images/service.py:generate_ending_image
  → prompts.ending_prompt(**slots) (app/images/prompts.py:77) → STYLE + REFERENCE_SUMMARY + 슬롯 문장 + NEGATIVE
  → generator.edit(prompt, [portrait_file_path]) (app/images/openai_images.py:73, gpt-image-2 edits, reference=초상화 1장)
```

핵심 확인 사항:

- **엔딩 이미지 프롬프트를 조립하는 함수는 `ending_prompt()`(images/prompts.py:77) 하나뿐**이고, 입력은 `compute_ending_slots()`가 만든 5개 문자열(location/posture/expression/props/distance)이 전부다.
- **엔딩 본문(`ending_body`), 제목(`ending_title`), evidence(대화 원문), unresolved는 이미지 프롬프트에 전혀 들어가지 않는다.** `ending.py:finalize_ending_text()`와 `compute_ending_slots()`는 완전히 분리된 별도 함수이며, 서로의 출력을 참조하지 않는다. `_finalize_turn12()`에서도 `finalize_ending_text()` 호출 후 `compute_ending_slots(session, card)`를 **세션 컬럼과 카드만 보고 독립적으로** 다시 계산한다.
- LLM(엔딩 생성 호출, `generate_ending`)은 title/body/unresolved만 생성한다(`LLMEndingOutput`, contracts.py:29). **이미지 장면을 설계하는 과정은 현재 코드에 전혀 없다.** LLM이 이미지에 관여하는 지점 자체가 없음.
- 슬롯은 전부 `Session` 컬럼(하드 상태값)의 조건문으로 결정되는 **결정론적 lookup**이지, 자유 생성이 아니다(compute_ending_slots, ending.py:84-113).

## 2. 왜 이미지가 비슷하게 나오는지 (코드 근거)

슬롯별 실제 variant 수와 실제 발생 빈도:

| 슬롯 | 코드상 variant 수 | 실제로 정상 완료(12턴) 플레이에서 나올 수 있는 값 |
|---|---|---|
| `location` | 4개 (`_LOCATION_BY_SCENE`, scene 1~4) | **사실상 1개 고정.** `location`은 `session.scene_id`로 결정되는데, `_TURN_TABLE`(engine/scene.py)상 턴 12는 항상 `scene_id=4`다. 정상적으로 12턴을 채워 끝난 회차는 예외 없이 `scene_id == 4` → `"Under the awning outside the shop, the door locked behind her"` 고정. 4가지 값 중 3가지(scene 1~3)는 **오직 조기 종료(`ended_early`)일 때만** 나올 수 있다. |
| `posture` | 2개 | **사실상 1개 고정.** `door_locked` 조건으로 갈리는데, `_finalize_turn12()`(turns.py:88)가 **무조건** `session.door_locked = True`를 실행한다. 조건 없는 대입이라 정상 완료 시 항상 `"Turning back for one last look"`. 다른 값은 조기 종료 시에만 나옴. |
| `expression` | 4개 | 실제로 변한다. `future_plan_accepted` > `contact_exchanged` > `book_owner/bookmark_owner==player` > 기본, 순서로 우선순위 있는 if-elif 체인이라 조건이 겹치면 앞쪽만 반영(예: 미래 약속도 하고 연락처도 교환했으면 "연락처 교환" 문구는 절대 안 나옴). |
| `props` | 3개 | 실제로 변한다. 카드 작성 여부 > 책 소유 여부 순서. |
| `distance` | 2개 | 사실상 거의 고정. `player_present`는 기본값 `True`이고, 이를 `False`로 바꾸는 유일한 경로는 `player_departed` 이벤트(`ALLOWED_EVENT_TYPES`에 있음)뿐이라 플레이어가 명시적으로 "자리를 뜬다"는 발언을 하지 않는 한 항상 `True` → `"Standing close together"` 고정. |

**결론: 정상적으로 12턴을 완주한 회차는 5개 슬롯 중 2개(location, posture)가 100% 고정, 1개(distance)도 사실상 고정이다. 실질적으로 변하는 건 `expression`(4갈래 중 하나)과 `props`(3갈래 중 하나)뿐이며, 이 둘도 우선순위 if-elif라 서로 배타적으로만 나타난다.**

정상 완료 기준 실질 조합 수 = 사실상 `expression(4) × props(3)` = 최대 12가지 텍스트 조합. 그런데 `ending_prompt()`가 만드는 문장에서 실제로 카메라/구도/배경/조명을 지시하는 것은 `STYLE_BLOCK`(모든 이미지 공통, 고정)과 `SCENE_PROMPTS`가 아니라 이 슬롯 문장뿐이므로, 이미지 모델 입장에서 매번 "같은 처마 아래, 같은 자세, 표정 한 단어와 손에 든 물건 한 단어만 다른" 프롬프트를 받는 셈이다. 표정 한 단어("A soft, quiet smile" vs "A composed, quiet expression")는 seed/reference 편집 특성상 이미지 모델이 크게 다른 그림을 그릴 유인이 거의 없다 — 이것이 "엔딩 텍스트는 다른데 이미지는 비슷하다"는 사용자 체감의 코드 레벨 원인이다.

추가 원인: `STYLE_BLOCK`이 "Vertical composition, full-body framing with headroom"으로 **카메라 구도를 모든 이미지(초상화·장면·엔딩 공통)에 못박아 둔다.** 엔딩 슬롯에는 camera/shot type/조명을 지시하는 요소가 전혀 없다.

## 3. LLM이 image_scene_spec(JSON)을 생성하고 서버가 검증하는 구조 — 가능성 검토

가능하다. 현재 엔딩 LLM 호출(`generate_ending`)은 이미 구조화 출력(JSON, `response_format={"type":"json_object"}`)을 쓰고 있고, `LLMEndingOutput`(contracts.py)에 필드를 추가하는 정도의 확장이라 **기존 계약을 깨지 않고 필드만 얹는 방식**으로 구현 가능하다. 다만 현재 구조에는 "LLM 출력 → 검증 → 확정" 파이프라인이 텍스트 상태값(`proposed_events`)에만 있고, 이미지 슬롯 쪽에는 전혀 없어서(2절 참고, `compute_ending_slots`는 LLM을 아예 거치지 않음) 이 검증 계층은 새로 만들어야 한다.

## 4. Q1~Q4

**Q1. `image_scene_spec` JSON 필드를 title/body/unresolved와 함께 추가 가능한가?**
가능하다. 수정 파일:
- `backend/app/llm/contracts.py` — `LLMEndingOutput`에 `image_scene_spec: dict | ImageSceneSpec` 필드 추가(Pydantic 서브모델 권장, 슬롯별 enum 제약 가능).
- `backend/app/llm/prompts.py` — `ENDING_RESPONSE_FORMAT_NOTE`에 새 JSON 필드 스펙 추가, `build_ending_system_prompt`에 "허용된 슬롯 값" 안내 추가.
- `backend/app/engine/ending.py` — `finalize_ending_text()`가 `result.output.image_scene_spec`을 받아 검증 함수에 넘기도록 수정, `compute_ending_slots()`를 대체하거나 병행하는 새 함수 추가.
DB migration은 불필요(기존 `ending_evidence`/`ending_unresolved`처럼 JSONB로 저장 가능, 굳이 저장 안 해도 됨 — 이미지 생성 시점에만 쓰고 버려도 무방).

**Q2. 엔딩 LLM이 이미지 장면을 설계할 만큼 충분한 정보를 받는가?**
`build_ending_system_prompt()`(prompts.py:226)가 이미 전달하는 것: PERSONA_YAML(외형 정책 포함), `confirmed_state_summary()`(help_status/book_owner/bookmark_owner/future_plan/contact_exchanged/player_present/card 상태), 문 잠글 때 player_present 여부, evidence 원문 quotes. **이미지 연출에 필요한 대부분의 사실관계(소품 소유, 카드 상태, player 존재 여부)는 이미 전달되고 있다** — 텍스트 엔딩 생성에 필요한 정보와 이미지 장면 설계에 필요한 정보가 사실상 같기 때문이다. 부족한 것: 현재 `scene_id`(마지막 장면이 어디였는지, 사실상 4로 고정이라 문제 아님), 그리고 "몇 번째 장면에서 어떤 사건이 일어났는지"의 순서 정보(예: 책을 준 게 장면 2인지 4인지) — 이건 `ConfirmedEvent.turn`엔 있지만 confirmed_state_summary에는 안 들어감. 연출에 필요하면 추가하면 되고, 필수는 아니다.

**Q3. 서버가 `image_scene_spec`을 confirmed state와 대조해 검증 가능한가?**
가능하다. 현재 `Session` 컬럼(book_owner, bookmark_owner, card.written, player_present, contact_exchanged, future_plan_accepted, door_locked)이 이미 딱 사용자가 예로 든 검증 조건들과 1:1로 대응한다:
- `book_owner != "player"`인데 LLM이 "holding the book" 선택 → reject/치환 가능(단순 if 문).
- `card.written == False`인데 "written card" 선택 → reject 가능.
- `player_present == False`인데 "standing close together" 선택 → reject 가능(이미 `compute_ending_slots`의 distance 로직이 이 필드를 그대로 쓰고 있음).
- `contact_exchanged == False`인데 관련 소품(휴대폰 등) 언급 → **다만 현재 코드에는 "휴대폰"이라는 프롭 자체가 정의돼 있지 않다.** 새 프롭을 늘릴 때만 해당하는 검증이라 지금은 해당 사항 없음.
- location 모순 → `scene_id` 기반으로 검증 가능하나, 2절에서 확인했듯 정상 완료 시 location은 이미 1개뿐이라 검증 대상 자체가 거의 없음.
검증 로직은 딕셔너리 기반 화이트리스트/필드-값 매핑으로 짜면 되고, `engine/state.py`의 `confirm_proposed_events`가 이미 쓰는 "허용 목록만 반영" 패턴을 그대로 재사용할 수 있다.

**Q4. 하이브리드(서버=사실관계, LLM=연출) 구조가 가능한가?**
가능하고, 오히려 현재 구조와 가장 자연스럽게 맞는다. 현재도 이미 "서버가 사실관계 슬롯(location/props/distance)을 결정 + 고정 문자열(posture/expression)을 대입"하는 구조이므로, **posture/expression을 LLM이 담당하는 자유도 있는 연출 슬롯으로 바꾸고, location/props(실제 소유물)/player_present/외형·의상 관련 문구는 계속 서버가 고정**하면 된다. STYLE_BLOCK의 "Vertical composition, full-body framing" 같은 구도 고정 문구도 이 기회에 LLM이 상황에 맞는 shot type(예: close-up vs wide shot)을 고를 수 있게 완화하는 선택지가 있다(다만 STYLE_BLOCK은 초상화/장면 이미지와 공통이라, 엔딩만 다른 구도를 쓰려면 엔딩 전용 스타일 블록을 분리해야 함 — 아래 9절 참고).

## 5. 이미지 다양성에 실제로 영향이 큰 요소

| 요소 | 영향 | 이유 |
|---|---|---|
| location | 큼 | 배경 전체가 바뀜(통로/카운터/창가/처마) — 다만 현재 정상 완료 시 사실상 고정이라 활용 안 되고 있음 |
| character action (구체적 행동) | 큼 | "웅크려 앉아 정리 중" vs "돌아서서 손을 흔듦" 등은 자세보다 훨씬 큰 실루엣 차이를 만듦 |
| body posture | 중간 | 서 있음/돌아섬 정도의 이분법은 큰 차이를 못 만듦(현재도 딱 2개뿐) |
| gaze (시선 방향) | 중간 | 카메라를 보는지 안 보는지는 표정과 함께 감정선을 바꾸지만 실루엣 변화는 작음 |
| facial expression | 작음 | 세로 풀샷 구도에서 얼굴이 차지하는 비중이 작아 표정 단어 하나로는 체감 차이가 거의 없음(사용자 우려와 일치) |
| camera angle | 큼 | 현재 전혀 다양화 안 됨(STYLE_BLOCK 고정) — 로우/하이 앵글은 인물 구도 자체를 바꿈 |
| camera distance/shot type | 큼 | "full-body" 고정 → close-up/medium/wide만 섞어도 즉시 다른 그림처럼 보임. 현재 전혀 미사용 |
| composition | 큼 | 인물이 프레임 중앙/구석/뒷모습 등으로 위치만 바뀌어도 체감 차이 큼. 현재 미사용 |
| foreground/background | 중간~큼 | 전경에 소품을 크게 배치하는지 여부가 그림 인상을 바꿈. 현재 소품은 "손에 든 것" 정도로만 언급 |
| lighting | 중간 | 현재 STYLE_BLOCK+SCENE_PROMPTS 수준에서 이미 장면별로 다르긴 하나(4번 장면=외부광), 엔딩 자체 조명 슬롯은 없음 |
| time/weather | 작음~중간 | 스토리상 시간대가 고정(21:00 근방)이라 변화 폭이 원래 작음 |
| props | 중간 | 현재 3갈래뿐이라 변화폭 제한적, 종류를 늘리면 중간~큼으로 상승 가능 |
| player presence | 중간 | on/off-screen 여부는 구도에 영향 있으나 현재 player_present가 사실상 거의 항상 True라 활용 안 됨 |
| character position in frame | 큼 | composition과 연동 — 현재 전혀 다양화 안 됨 |

**결론: 지금 코드가 다양화하고 있는 요소(expression, 좁은 의미의 props)는 실제로는 영향이 작은 축에 속하고, 영향이 큰 축(location, camera shot/angle, composition, character action, character position)은 정상 완료 시 거의 다양화되지 않고 있다.** 이게 "텍스트는 다른데 그림은 비슷하다"는 체감의 핵심 원인이다.

## 6. Portrait reference 1장 유지 가능 여부

가능하다. `openai_images.py`의 `edit()`는 `reference_image_paths: list[str]`를 받는 인터페이스이고, 현재도 장면 1~4·엔딩 전부 초상화 1장만 참조로 쓴다(`portrait_file_path` 하나만 전달). **location/posture/composition/camera distance/lighting을 다양화하는 것은 참조 이미지 개수와 무관한, 순수 텍스트 프롬프트 변경**이므로 추가 reference 이미지는 필요 없다. GPT Image 2의 edit 엔드포인트는 참조 인물의 동일성(얼굴·의상)을 유지하면서 포즈·배경·구도를 프롬프트로 바꾸는 것을 지원하는 용도 자체가 이런 편집이라, 오히려 지금처럼 슬롯 표현이 밋밋한 것이 활용도를 낮추고 있다.

## 7. 대안 비교

**A. 기존 slot만 확장**
- 내용: `compute_ending_slots()`의 각 slot에 값 종류를 늘리고, `posture`/`expression`에 더 많은 분기 추가, `camera_shot`/`lighting` 같은 새 slot 추가.
- 장점: 구현이 가장 간단(순수 파이썬 if-elif 추가). LLM 호출/검증 계층 불필요. 환각 위험 없음(전부 서버 결정론적).
- 단점: **근본 원인이 해결 안 됨.** 2절에서 확인했듯 정상 완료 시 실제로 갈리는 축은 `Session` 컬럼 몇 개(book_owner, bookmark_owner, contact_exchanged, future_plan_accepted, card.written)뿐이라, slot 종류를 아무리 늘려도 실제 발생 가능한 "의미 있는 조합"의 개수는 그 컬럼들의 실제 조합 수(대략 2^4~2^5 = 16~32가지, 우선순위 if-elif라 실제로는 더 적음)를 못 넘는다. **연출(카메라/구도/행동)까지 다양화하려면 결국 "각 state 조합마다 사람이 미리 연출 문구를 다 써놓는" 작업이 필요**해서, 수동으로 posture 10개·expression 8개를 짜 넣어도 그 각각이 실제 상태와 논리적으로 잘 붙는지 사람이 다 검토해야 함(조합 폭증 대비 저작 비용 큼).
- 수정 파일: `backend/app/engine/ending.py`(compute_ending_slots만).
- 예상 효과: 낮음~중간. state 조합 수 자체가 다양성의 상한이라 한계가 뚜렷함.

**B. LLM image_scene_spec + 서버 검증**
- 내용: 3~4절 방식. LLM이 매번 새로운 연출(JSON)을 만들고 서버가 사실관계 위반만 걸러냄.
- 장점: 실제 대화 내용(evidence, 어느 장면에서 어떤 사건이 있었는지)까지 반영한 연출이 가능해 "state 조합 수"라는 상한을 벗어남 — 같은 state 조합이라도 대화 뉘앙스에 따라 다른 그림이 나올 수 있음. 저작 비용(사람이 문구를 일일이 안 써도 됨) 낮음.
- 단점: 검증 로직을 새로 설계·구현해야 함(비어있는 계층). 환각 위험 있음(LLM이 화이트리스트에 없는 값을 낼 수 있어 sanitize 필요, 예: enum 강제 + fallback). 구조화 출력 실패 시 폴백(`degrade_ending_to_fallback`) 로직도 이미지 스펙에 대해 별도로 만들어야 함.
- 수정 파일: `backend/app/llm/contracts.py`(스키마 추가), `backend/app/llm/prompts.py`(프롬프트에 스펙 지시 추가), `backend/app/engine/ending.py`(검증+최종 슬롯 병합 로직 추가), `backend/app/images/prompts.py`(새 슬롯을 받는 ending_prompt 확장).
- 예상 효과: 큼. 다만 순수 B(전부 LLM이 정함)는 사용자가 우려하는 "날조" 위험을 서버가 100% 못 걸러낼 수도 있음(LLM이 화이트리스트 밖 자유 텍스트를 만들면 그 문장 자체의 의미까지 검증하긴 어려움 — enum 강제가 아니면 사실상 C에 가까워짐).

**C. 하이브리드 (서버=사실관계, LLM=연출)**
- 내용: 4절 Q4 방식. 서버가 여전히 book_owner/bookmark_owner/card.written/player_present/location(scene_id) 등 "사실"을 문자열로 확정하고, LLM은 그 사실을 위반하지 않는 한도 내에서 camera/action/gaze/mood/lighting 같은 "연출"만 enum 형태로 고름(자유 텍스트가 아니라 서버가 제공한 후보 목록 중 선택하게 하면 검증이 단순 in-list 체크로 끝남).
- 장점: B의 다양성 이점을 대부분 가져오면서, enum 강제로 환각 위험을 A 수준까지 낮출 수 있음. 사실관계 슬롯(location/props/distance)은 그대로 재사용 가능해 기존 구조 파괴가 적음.
- 단점: 설계 복잡도가 A보다는 높음(LLM 호출 1단계 추가 없이 기존 엔딩 호출에 필드만 얹으면 되므로 API 호출 수는 안 늘어남 — 이 부분은 B와 동일하게 저렴함).
- 수정 파일: B와 거의 동일 + `backend/app/images/prompts.py`에 camera/action/mood enum별 영문 조각 사전 추가(현재 SCENE_PROMPTS처럼 미리 정의된 조각 방식 재사용).
- 예상 효과: 큼, 환각 위험은 B보다 낮음.

| 방식 | 이미지 다양성 | 구현 난이도 | 기존 구조 변경 | 환각/불일치 위험 | 추천도 |
|---|---|---|---|---|---|
| A | 낮음~중간 | 낮음 | 작음(함수 1개) | 없음 | 낮음 |
| B | 큼 | 중간~높음 | 중간(신규 검증 계층) | 중간~높음(자유 텍스트 시) | 중간 |
| C | 큼 | 중간 | 중간(신규 검증 계층, 단 enum 재사용) | 낮음(enum 강제) | **높음** |

## 8. 추천

**C(하이브리드)를 추천한다.**

사용자 요구사항 대조:
- "엔딩 텍스트 차이가 이미지에도 눈에 띄게 반영" → C는 카메라/구도/행동을 LLM이 실제 대화 뉘앙스를 보고 고르므로 A의 한계(state 조합 수 상한)를 벗어난다.
- "캐릭터 외형 동일 유지" → 참조 이미지 방식 그대로 유지, 슬롯은 연출만 다양화하므로 영향 없음(6절).
- "발생 안 한 사건 날조 금지" → B의 자유 텍스트 방식보다 C의 enum 강제 방식이 이 요구를 훨씬 안전하게 만족한다. 서버가 사실관계 슬롯(위치·소품·player_present)은 계속 직접 결정하고, LLM은 그 틀 안에서 "어떻게 보여줄지"만 고르므로 논리적 모순 자체가 구조적으로 발생하기 어렵다.
- "기존 시스템 최대 재사용" → `compute_ending_slots()`의 사실관계 로직은 그대로 두고 연출 슬롯만 LLM 선택으로 대체 → 기존 코드 삭제가 거의 없다.
- "DB/API/UI 대규모 재작업 회피" → 아래 9절 참고, DB migration 불필요, API 계약(프론트 접점) 불변 가능.

## 9. 추천 방식(C) 기준 실제 수정 범위

| 파일 | 왜 수정하는지 | 변경 종류 | DB migration | API contract 변경 | frontend 수정 |
|---|---|---|---|---|---|
| `backend/app/llm/contracts.py` | `LLMEndingOutput`에 연출 필드(예: `camera`, `action`, `gaze`, `mood`, `lighting` — 각각 enum 후보 중 하나) 추가 | 스키마 확장 | 불필요 | 불필요(내부 전용 필드, EndingResponse에 안 실음) | 불필요 |
| `backend/app/llm/prompts.py` | `ENDING_RESPONSE_FORMAT_NOTE`에 연출 필드 JSON 스펙과 각 필드의 허용 후보 목록 명시, `build_ending_system_prompt`에 어떤 사실을 위반하면 안 되는지 안내 추가 | 프롬프트 텍스트 확장 | 불필요 | 불필요 | 불필요 |
| `backend/app/engine/ending.py` | LLM이 낸 연출 값이 화이트리스트(enum)에 있는지 검증하고(없으면 기본값으로 폴백), `compute_ending_slots()`가 만드는 사실관계 슬롯과 합성하는 함수 추가. `finalize_ending_text()`가 이 결과를 함께 반환하도록 확장 | 신규 검증/합성 로직 + 기존 함수 시그니처 확장 | 불필요(연출 값을 DB에 영구 저장할 필요 없음 — 이미지 생성 직후 버려도 됨. 저장하고 싶다면 JSONB 컬럼 추가 시 migration 필요하지만 필수 아님) | 불필요 | 불필요 |
| `backend/app/images/prompts.py` | `ENDING_TEMPLATE`을 확장해 연출 슬롯(camera/action/gaze/mood/lighting)을 문장에 추가, 각 enum 값 → 영문 문구 매핑 사전 추가(SCENE_PROMPTS처럼 미리 정의된 조각), STYLE_BLOCK의 "Vertical composition, full-body framing" 고정 문구를 엔딩에서만 완화하려면 엔딩 전용 스타일 조각 분리 필요 | 프롬프트 조립 로직 확장 | 불필요 | 불필요 | 불필요 |
| `backend/app/api/turns.py`, `backend/app/api/ending.py` | `_finalize_turn12`/`retry_ending_image`가 `compute_ending_slots` 대신(또는 함께) 새 합성 함수를 호출하도록 배선 변경 | 호출부 교체 | 불필요 | 불필요 | 불필요 |

**모든 변경이 백엔드 내부(`backend/app/`)에서 끝난다.** `EndingResponse`(schemas.py)나 `docs/api-contract.md`에 새 필드를 노출할 필요가 없으므로 — 프론트는 지금처럼 `image.status`/`image.url`만 폴링하면 되고, 이미지 자체가 다양해지는 것 외에 API 응답 형태는 그대로다. **frontend(Codex) 수정은 필요 없다.**

---

# 스토리 리디자인 제약사항

(이 섹션은 이전에 작성된 `STORY_REDESIGN_CONSTRAINTS.md`와 별개로, 이번 조사(엔딩 이미지 한정)의 최종 요약이다.)

## 결론

- **현재 엔딩 이미지가 비슷한 핵심 원인**: `compute_ending_slots()`의 5개 슬롯 중 `location`과 `posture`가 정상적으로 12턴을 완주한 회차에서는 코드 로직상(턴12는 항상 scene_id=4, door_locked는 무조건 True) **사실상 100% 고정값이고**, `distance`도 player_present가 거의 항상 True라 사실상 고정이다. 실제로 변하는 건 `expression`(4갈래 우선순위 조건)과 `props`(3갈래)뿐인데, 이 둘은 세로 풀샷 구도에서 체감 영향이 작은 축(5절 참고)이다. 또한 엔딩 본문/원문 근거가 이미지 프롬프트에 전혀 반영되지 않는다.
- **가장 추천하는 구조**: C(하이브리드) — 서버가 사실관계(위치·실제 소품·player 존재)를 계속 결정하고, LLM이 대화 맥락을 보고 카메라/행동/시선/분위기/조명을 **enum 후보 중에서** 고르게 해 다양성을 확보하면서 날조 위험은 화이트리스트로 차단.
- **기존 portrait reference(1장) 유지 가능 여부**: 가능. 연출 다양화는 순수 텍스트 프롬프트 변경이라 참조 이미지 구조와 무관.
- **DB migration 필요 여부**: 불필요(연출 값을 영구 저장하지 않아도 됨).
- **frontend 변경 필요 여부**: 불필요.
- **API contract 변경 필요 여부**: 불필요.
- **예상 수정 파일**: `backend/app/llm/contracts.py`, `backend/app/llm/prompts.py`, `backend/app/engine/ending.py`, `backend/app/images/prompts.py`, `backend/app/api/turns.py`, `backend/app/api/ending.py` (전부 backend 내부).
- **기존 시스템을 크게 깨지 않고 구현 가능한가**: **YES**.

### ChatGPT에게 전달할 핵심 분석 결과

- 목표 플레이타임 10~15분, 4장면×3턴=12턴 고정, 캐릭터 1명(한서윤), 회차당 이미지 6장(초상화1+장면4+엔딩1), 참조 이미지는 초상화 1장만 사용(gpt-image-2 edits API).
- 엔딩 이미지는 서버가 결정하는 5개 슬롯(location/posture/expression/props/distance)을 문장에 채워 넣는 완전 결정론적 방식이며, LLM은 엔딩 이미지 설계에 전혀 관여하지 않는다.
- 문제: 정상 완주 시 location(4갈래 중 사실상 1개 고정: 마지막 장면=처마 밑)과 posture(2갈래 중 사실상 1개 고정: 문 잠그는 포즈)가 거의 항상 같은 값으로 고정되고, distance도 거의 항상 같다. 실제로 갈리는 건 expression(4갈래)·props(3갈래)뿐인데 이 둘은 세로 풀샷 인물컷에서 시각적 임팩트가 작은 요소다. 엔딩 본문/대화 근거는 이미지 프롬프트에 전혀 반영 안 됨.
- 다양성에 실제 임팩트가 큰 요소: 카메라 앵글/거리(shot type), 프레임 내 인물 위치(composition), 구체적 행동(character action) — 이 세 가지는 현재 전혀 다양화되지 않고 있음(구도 자체가 모든 이미지 공통으로 "세로, 풀바디" 고정 문구).
- 채택 방향: 서버는 계속 "사실"(실제 소품 소유, player 존재 여부, 장소)만 결정하고, 엔딩 텍스트를 생성하는 LLM 호출에 "연출" 필드(카메라/행동/시선/분위기/조명)를 enum 후보 중에서 고르게 하는 필드를 추가 — 자유 텍스트가 아니라 화이트리스트 선택이라 사실 위반(날조) 위험이 낮음.
- 캐릭터 외형·의상은 계속 고정(story.md 규칙 그대로), 참조 이미지 1장 재사용 그대로 유지.
- 순수하게 백엔드 내부 변경만으로 가능: DB migration 불필요, API 계약 불변, 프론트 수정 불필요.
- 스토리를 재설계할 때 참고할 점: "책→책갈피→카드→문 잠금" 같은 고정 사건 자체를 바꾸더라도, 그 사건이 만들어내는 최종 state(누가 무엇을 가졌는가, 마지막에 함께 있었는가)만 명확히 정의되면 이 이미지 다양화 구조에 그대로 얹을 수 있다. 즉 스토리 재설계와 엔딩 이미지 다양화는 독립적으로 진행 가능.
