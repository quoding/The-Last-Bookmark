# 스토리 리디자인을 위한 현재 구현 제약사항 조사

> 목적: 스토리 개선안을 제안하지 않는다. 현재 코드/DB/프롬프트/UI가 실제로 무엇을 고정하고
> 있는지, 무엇이 자유롭게 바뀔 수 있는지만 근거를 들어 조사한다.
> 근거: `backend/app/` 실제 코드(models.py, engine/*, llm/*, images/*, api/*, schemas.py)와
> `docs/story.md`, `docs/ui-spec.md`, `docs/api-contract.md`를 직접 읽고 확인했다.
> 문서와 실제 코드가 다른 지점은 각 절에서 "문서 vs 실제"로 명시한다.

---

# 1. 현재 게임의 전체 플레이 구조

**근거 파일:** `backend/app/engine/scene.py`, `backend/app/api/turns.py`, `backend/app/api/card.py`,
`backend/app/api/end.py`, `backend/app/api/ending.py`, `backend/app/engine/state.py`

- **전체 장면 수:** 4개. `backend/app/engine/scene.py`의 `SCENES` 딕셔너리에 `{1: "마지막 손님", 2: "남겨둔 책", 3: "쓰지 못한 한 문장", 4: "문을 닫기 전에"}`로 하드코딩.
- **장면별 턴 수:** 정확히 3턴씩 고정. `_TURN_TABLE`(턴 1~12 → (시각, 장면ID))이 코드에 리터럴로 박혀 있다.
- **총 턴 수:** `MAX_TURNS = 12`(상수).
- **각 장면의 시작/종료 조건:** 순수하게 **완료된 턴 번호**로 결정된다. `_TRANSITIONS_AFTER = {3: 2, 6: 3, 9: 4}` — 턴 3·6·9가 완료되는 순간 다음 장면으로 넘어간다. 장면 안에서 "무엇이 일어났는가"는 전환 조건에 전혀 영향을 주지 않는다. 즉 사건 기반이 아니라 **턴 카운터 기반**이다.
- **장면 전환을 누가 결정하는가:** **서버**. `app/api/turns.py:submit_turn`이 `get_turn_info(new_turn)`으로 매 턴마다 서버가 계산하고, `session.scene_id`를 갱신한다. LLM 출력에는 장면 정보가 전혀 없다(`llm/contracts.py`의 `LLMTurnOutput`에는 `reply`/`narration`/`proposed_events`뿐). 프론트도 서버가 내려주는 `scene` 필드를 그대로 표시할 뿐 전환을 결정하지 않는다.
- **조기 종료 가능 여부:** 가능. `POST /api/sessions/{id}/end`(`app/api/end.py`)로 언제든(진행 중이면) 호출 가능. `session.status = "ended_early"`로 바뀌고 그 시점까지 확정된 사건만으로 엔딩이 생성된다. `door_locked`는 확정되지 않는다(코드에서 `_finalize_turn12`만 `door_locked = True`를 설정하고, `end_early`는 이를 건드리지 않음 — story.md/ui-spec.md 서술과 실제 코드가 일치).
- **엔딩이 발생하는 정확한 조건:** 두 경로뿐이다.
  1. `submit_turn` 또는 `submit_card`에서 `turn_info.is_final_turn`(= 완료 턴이 12)이면 `_finalize_turn12` 호출 (`app/api/turns.py`, `app/api/card.py`가 이 함수를 공유).
  2. `POST /api/sessions/{id}/end` 호출 시 즉시.
  둘 다 `engine/ending.py:finalize_ending_text`를 호출해 LLM으로 제목·본문·미해결목록을 생성하고, `background_tasks`로 엔딩 이미지 생성을 비동기로 넘긴다.
- **이야기 속 시간과 턴의 연결:** `_TURN_TABLE`이 턴→시각의 1:1 매핑을 정적으로 갖고 있다(20:32, 20:34, 20:37, ..., 21:00). LLM 출력에서 시각을 추출하는 코드는 없다 — 완전히 서버 상수.
- **문서 vs 실제:** 이 장(scene.py)은 문서(story.md 6장, ui-spec.md 6장)와 정확히 1:1로 일치한다. 차이 없음.

---

# 2. 절대로 또는 가급적 유지해야 하는 구조 (A/B/C 등급)

- **A = 사실상 고정** (바꾸려면 여러 코드/DB/API/프롬프트/이미지를 동시에 고쳐야 하거나 완성된 구조를 깨뜨림)
- **B = 변경 가능하지만 비용 있음** (여러 파일 수정 필요, 그러나 구조 자체는 안 깨짐)
- **C = 스토리만 바꾸면 됨** (프롬프트·텍스트·설정 상수 수준)

| 요소 | 등급 | 근거 |
|---|---|---|
| 장면 개수(4개) | A | `SCENES` 딕셔너리 키가 1~4로 코드 곳곳(이미지 프롬프트, 엔딩 location 매핑, DB `scene_id` 정수 컬럼, UI 장면 목록)에서 가정된다. 개수를 바꾸려면 `scene.py`, `images/prompts.py`의 `SCENE_PROMPTS`, `engine/ending.py`의 `_LOCATION_BY_SCENE`, 프론트 장면 배열까지 전부 같이 고쳐야 한다. |
| 장면당 턴 수(3턴 고정) | A/B | `_TURN_TABLE`이 리터럴 매핑이라 장면당 턴 수를 바꾸는 것 자체는 이 표만 다시 쓰면 된다(B). 다만 ui-spec.md 13장에 이미 "장면4를 4턴으로 늘리는 대안"이 문서화돼 있어 표 구조 자체는 이미 이 변경을 염두에 두고 설계됨. 장면마다 다른 턴 수를 주는 것도 표만 바꾸면 되므로 실질적으로 B.
- 단, **총 턴수·장면수 자체를 프론트와 무관하게 서버만 바꿔도** 스키마·API 계약은 안 바뀐다(턴 수는 API 응답에 숫자로만 나감). |
| 총 턴 수(12) | B | `MAX_TURNS` 상수 하나와 `_TURN_TABLE`의 항목 수만 바꾸면 된다. UI는 `is_final_turn`(서버가 내려주는 bool)만 보므로 "몇 턴째" 하드코딩이 없다. 단, ui-spec.md 3.1(“30초 안에 끝나야”), 11장(시간 배분표) 등 문서상의 시간 가정과 재조정 필요 — 문서 수정 비용. |
| 장면별 시간(20:32, 20:34 …) | C | `_TURN_TABLE`의 문자열 값일 뿐. UI는 서버가 준 문자열을 그대로 표시(`story_time`). 자유 변경. |
| 플레이타임 10~15분 구조 | B | 강제하는 코드가 없다(실시간 타이머 없음, ui-spec.md 6장 "강제 종료하지 않는다"). 실측 이미지 생성 지연(20~30초/장, CLAUDE.md 가정 5초와 실측 다름 — 아래 6장 참고)과 LLM 응답 길이 제약(120~200자)이 실질적 플레이타임을 결정한다. 시간 자체를 조절하려면 턴수·응답길이 제약을 바꿔야 하므로 B. |
| 장소 개수(4곳: 통로/카운터/창가/문 앞) | A | 장면 수와 1:1 대응(장면마다 공간 하나). 이미지 프롬프트(`SCENE_PROMPTS`)와 엔딩 로케이션 매핑(`_LOCATION_BY_SCENE`)이 장면ID로 색인된 정적 딕셔너리라 장소 텍스트 자체(예: "서가 사이 통로"→"다른 공간 이름")는 C이지만, 장소 "개수"를 바꾸려면 장면 수와 함께 바뀌어야 하므로 A. |
| 캐릭터 수(서윤 1명 + 플레이어) | A | 1인 캐릭터를 전제로 시스템 프롬프트 구조(`PERSONA_YAML` 단일 character 블록), 이미지 프롬프트(NEGATIVE_BLOCK에 "No other people in frame" 명시), 참조 이미지 1장 재사용 구조 전체가 짜여 있다. 2인 이상 캐릭터로 확장하려면 프롬프트 조립, 이미지 생성 파이프라인(참조 이미지 슬롯), DB 스키마(현재 캐릭터별 컬럼이 아니라 세션 단일 컬럼) 전부 재설계 필요. |
| 캐릭터 이름/성격/관계(한서윤, 27세, 단골 관계 등) | C | `llm/prompts.py`의 `PERSONA_YAML` 문자열 하나를 고치면 된다. 코드가 이 값의 내용을 파싱하거나 조건 분기하지 않는다(그냥 프롬프트에 통째로 삽입). DB에도 캐릭터 이름을 저장하는 컬럼이 없다(이미지 프롬프트 쪽 `_CHARACTER_TEMPLATE`에도 캐릭터 이름 언급 없음 — "A 27-year-old Korean woman" 식 서술이라 나이·성별을 바꾸려면 이미지 프롬프트도 같이 고쳐야 함, 아래 참고). |
| 시작 상황(폐점 서점) | B | `OPENING_MESSAGES`(고정 4개 메시지, `engine/opening.py`)와 `PERSONA_YAML`/`SCENARIO_YAML`(둘 다 텍스트 상수)만 고치면 이야기 설정 자체는 바뀐다. 코드가 "폐점"이라는 의미를 실행 조건으로 사용하는 곳은 없다(모두 텍스트). 다만 상황을 완전히 다른 장르(예: 서점이 아닌 공간)로 바꾸면 이미지 프롬프트의 `STYLE_BLOCK`/`SCENE_PROMPTS`/`_CHARACTER_TEMPLATE`의 의상 묘사(니트, 앞치마)까지 전부 재작성해야 하므로 B. |
| 폐점 설정 자체 | B | 위와 동일. `door_locked`라는 state 변수명과 `event_type: door_locked`가 DB/코드에 있지만, 이 값이 "정말 문이 잠기는 사건"이어야 할 논리적 필연성은 없다 — 그냥 "장면4에서 확정되는 불리언 사건 플래그" 하나일 뿐이라 의미만 바꾸면 됨(용도가 "마지막 종료 신호"라는 역할만 유지되면 됨). |
| 책방이라는 장소 | B | 이미지 STYLE/SCENE 프롬프트, 의상(`_CHARACTER_TEMPLATE`의 앞치마), `_LOCATION_BY_SCENE` 텍스트 전부가 "서점"을 전제로 쓰여 있다. 장소를 바꾸려면 이미지 프롬프트 세트 전체(포트레이트+4장면+엔딩 로케이션)를 다시 써야 한다 — 텍스트 교체만으로 되지만 범위가 넓어 B. |
| 책 (오브젝트) | C~B | `book_owner` state 컬럼(A급 상태값, 4절 참고)이 있지만 "책"이라는 대상 자체는 텍스트일 뿐이다. `book_given`/`book_declined` 이벤트가 `book_owner`를 바꾸는 로직(`engine/state.py`)은 오브젝트 이름에 의존하지 않는다("선물 오브젝트 A"로 봐도 무방). 단, 이미지 프롬프트(장면2 "a single short story collection")와 엔딩 props("Holding the book in one hand")에 하드코딩된 영문 묘사가 있어 오브젝트 성격을 바꾸면 그 문자열들도 고쳐야 한다(B).
- **DB/스키마가 "책"이라는 개념을 기대하는가:** 아니오. 컬럼명이 `book_owner`(값은 `"seoyun"`/`"player"` 문자열)일 뿐 책 관련 메타데이터(제목 등)는 저장하지 않는다. 이름을 바꾸는 것도 자유(마이그레이션 없이 의미만 재정의 가능). |
| 책갈피 | C~B | `bookmark_owner` 컬럼, `bookmark_given` 이벤트 — 책과 동일한 구조. 소유권 이진 상태(서윤/플레이어)만 갖고, "책갈피"라는 텍스트 자체는 프롬프트·이미지 서술에만 존재한다. 완전히 다른 소품으로 교체 가능(구조는 그대로, 텍스트만 교체). |
| 카드 | A | 전용 테이블 `Card`(models.py), 전용 API(`POST /api/sessions/{id}/card`), 전용 UI 컴포넌트(ui-spec.md 7장 전체 절), 80자 제한 상수(`CARD_MAX_VISIBLE_CHARS`), `card_available`(장면3 이상 && 미결정 시에만 true) 로직, 엔딩 응답의 별도 `card` 필드까지 — 다른 어떤 소품보다 구조적으로 깊게 박혀 있다. "빈 카드에 한 문장 남기기"라는 인터랙션 자체(글쓰기 UI, 결정 여부 `decided` 플래그, 결정 턴 소비 규칙)를 없애려면 API 엔드포인트·스키마·프론트 컴포넌트를 통째로 제거/재설계해야 한다. 다만 카드에 "무엇을 쓰는가"의 서사적 의미(무엇을 상징하는 카드인지)는 자유. |
| 문 잠금 | B | `door_locked` bool 컬럼 + `_finalize_turn12`에서만 세팅되는 로직 + 엔딩 이미지 posture 분기("Turning back for one last look" vs 그대로)에 쓰인다. "문을 잠근다"는 서사적 의미 없이 "마지막 턴에 확정되는 사건 플래그"로 봐도 로직이 그대로 성립하므로, 텍스트/이미지 프롬프트만 바꾸면 다른 마무리 사건("불 끄기", "간판 내리기" 등)으로 대체 가능(B, 이미지 프롬프트 수정 필요). |
| 마지막 엔딩(이미지+텍스트 생성) | A | 엔딩 생성 파이프라인 자체(LLM 호출 구조, evidence 선택, 슬롯 기반 이미지 프롬프트)는 구조적으로 고정. 다만 각 슬롯의 **내용**(어떤 문장이 나오는지)은 전부 C. |
| 카드 작성 UI | A | 위 "카드" 항목과 동일 — 전용 컴포넌트·엔드포인트가 있어 구조 자체를 없애는 건 A급 비용. |
| 외형 선택 | A | 7축 프리셋 시스템(`PRESETS` dict, `PresetSelection` pydantic 모델, DB `presets` JSONB 컬럼, 이미지 CHARACTER 템플릿의 플레이스홀더)이 API 계약(`docs/api-contract.md`)에 필드로 박혀 있다. 축 개수·이름을 바꾸면 `PresetSelection` 스키마, `_CHARACTER_TEMPLATE`의 포맷 플레이스홀더, 프론트 드롭다운을 전부 같이 고쳐야 한다. |
| 초상화 생성 | A | 세션 생성 흐름 자체가 "초상화 성공 없이는 세션을 시작하지 않는다"는 동기 게이트로 짜여 있다(`create_session`가 실패해도 세션 row는 만들어지지만 `portrait_image_id`가 없으면 `/start`가 409를 낸다). 모든 후속 이미지(장면 4장, 엔딩)가 이 초상화 파일 경로를 참조로 사용하는 구조. |
| 장면 이미지 생성 | B | 타이밍(회차 생성 직후 백그라운드 시작, `/start`가 기다리지 않음)은 최근에 이미 바뀐 이력이 있다(worklog 기록: 장면1도 비동기로 전환). 이 부분은 코드 변경 없이 스토리만 바꿔도 영향 없음 — 이미 유연하게 만들어져 있다. |
| 엔딩 이미지 생성 | B | 슬롯 값(`compute_ending_slots`)이 현재 5개 상태값(book_owner, bookmark_owner, card, future_plan_accepted, contact_exchanged, door_locked, player_present)의 조합으로 결정된다. 상태값 자체를 바꾸면 이 함수도 같이 고쳐야 한다. |
| 이미지 생성 타이밍(포트레이트 동기 / 장면 비동기 / 엔딩 비동기) | B | `BackgroundTasks` 기반 구조 자체(A급, 6장 참고)는 유지하되 "어느 시점에 어떤 이미지를 트리거하는가"는 `sessions.py`/`turns.py`의 함수 호출 위치 몇 곳만 옮기면 됨. |
| 대화 저장 | A | `Message` 테이블(턴·kind·record_type·text)이 전체 UI(대화 로그, 엔딩 근거 인용)의 기반. 구조 자체는 스토리 내용과 무관하게 그대로 유지 가능해야 함(오히려 스토리를 바꿔도 이 테이블 구조는 안 건드려도 됨 — 그래서 "유지 항목"이라기보다 "스토리 변경과 무관하게 이미 유지되는 인프라"). |
| 기억/상태 저장(`ConfirmedEvent`, `SceneEvent`) | A(구조)/C(내용) | 허용목록 기반 상태 확정 구조(`engine/state.py`의 `APPLIERS`)는 "LLM 제안 → 서버 검증 확정"이라는 핵심 설계 원칙(CLAUDE.md 5.1)을 구현하는 뼈대라 유지 권장. 다만 그 안의 **개별 이벤트 타입 9개**(help_offered, book_given 등)는 전부 story.md에 종속된 이름이라 새 스토리에 맞는 이벤트로 완전히 갈아끼울 수 있다(C~B, 아래 4장 참고). |
| 관계 수치(trust/closeness/tension) | C(사실상 죽은 코드) | `Session` 모델에 컬럼은 있지만(models.py) **API 응답에도, 어떤 로직 분기에도 전혀 쓰이지 않는다.** `engine/state.py`, `engine/ending.py`, `llm/prompts.py` 어디에도 이 세 값을 읽거나 쓰는 코드가 없다(디폴트값만 갖고 컬럼에 얹혀있음). 실질적으로 미사용 컬럼이라 자유롭게 없애거나 새 수치로 대체해도 다른 로직에 영향 없음. |
| 소품 소유권(book_owner, bookmark_owner) | B | 상태값 자체(이진 소유권 패턴)는 재사용 가능한 구조. 이름과 의미만 바꾸면 다른 소품 소유권 추적에도 그대로 쓸 수 있음. |
| 연락/약속 관련 상태(future_plan, future_plan_accepted, contact_exchanged) | B | "제안 vs 합의" 2단계 패턴(`future_plan_proposed`가 텍스트 저장, `future_plan_accepted`가 별도 확정 필요)은 story.md 8.3의 서사 규칙("제안만으로는 약속이 아니다")을 그대로 구현한 것. 이 패턴 자체는 스토리가 바뀌어도 재사용 가능(다른 종류의 "제안→합의" 관계에도). |
| 엔딩 생성에 들어가는 데이터 | B | `select_evidence`가 참조하는 `EVIDENCE_EFFECT_TEXT` 딕셔너리(5개 이벤트 타입→효과 문장)와 `confirmed_state_summary`가 참조하는 상태값들은 전부 현재 9개 이벤트/상태값에 강결합. 이벤트 종류를 바꾸면 이 두 곳도 같이 고쳐야 함. |
| **(추가 발견) 이미지 참조 구조(초상화 1장만 참조)** | A | CLAUDE.md 9.2/story.md 어디에도 없는 코드 레벨 제약: `images/service.py`(엔딩·장면 생성 함수들이 전부 `portrait_path` 하나만 인자로 받음)와 프롬프트의 `REFERENCE_SUMMARY`("The same woman as in the reference image")가 참조 이미지가 정확히 1장이라는 것을 전제로 짜여 있다. 여러 인물이나 여러 참조 이미지가 필요한 스토리로 바꾸려면 이미지 생성 파이프라인 재설계가 필요. |
| **(추가 발견) 카드 80자 제한 등 UI 상수와 스토리 결합** | C | `CARD_MAX_VISIBLE_CHARS = 80`은 `api/card.py`의 상수 하나. 카드에 쓰는 문장의 **내용**은 완전히 자유. |

---

# 3. 장면별로 코드에 박혀 있는 고정 요소

## Scene 1 (마지막 손님 / 서가 사이 통로, 턴 1~3)

- **코드상 반드시 발생하는 사건:** 없음. 턴 전환(3턴 완료 시 장면2로) 외에는 코드가 강제하는 사건이 없다. `engine/state.py`의 어떤 `APPLIERS` 함수도 "장면 1에서만" 실행 가능하도록 제한돼 있지 않다(`_apply_book_given` 등은 `session.scene_id >= 2`만 검사 — 장면 1에서는 조건 미충족으로 조용히 무시될 뿐).
- **프롬프트에서만 정해지는 사건:** `llm/prompts.py`의 `SCENE_BRIEFS[1]` — "3턴째에 카운터 아래에 둔 책을 꺼낸다"는 순수 텍스트 지시일 뿐 서버가 검증하지 않는다. LLM이 이 지시를 따르지 않아도 코드는 감지·강제하지 않는다.
- **UI가 가정하고 있는 사건:** 없음. UI는 서버가 준 메시지·장면 상태만 렌더링.
- **생성 이미지가 가정하고 있는 상황:** `images/prompts.py`의 `SCENE_PROMPTS[1]` — "포장 상자, 방금 상자를 내려놓고 돌아보는 자세". 이 이미지는 장면 진입 시 고정적으로 한 번 생성되고 대화 내용과 무관하게 항상 같은 그림이다(대화 결과 반영 없음, 6장 참고).
- **상태 변수 변경:** 코드 강제 없음(전부 선택적: help_offered/help_completed는 장면 제약 없음).
- **다음 장면으로 넘겨야 하는 데이터:** 없음. `scene_id` 정수 하나가 넘어갈 뿐 장면 간 전달되는 특별한 payload는 없다(모든 state는 세션 전체에 공유되는 컬럼이라 "장면이 끝나면서 넘기는" 개념 자체가 없음 — 그냥 계속 같은 Session row를 갱신).

## Scene 2 (남겨둔 책 / 카운터 앞, 턴 4~6)

- **코드상 반드시 발생하는 사건:** 없음. `book_given`/`bookmark_given` 이벤트는 `scene_id >= 2`일 때만 유효하게 적용되지만(`engine/state.py`), LLM이 이 이벤트를 제안하지 않으면 영원히 일어나지 않을 수 있다 — 강제 발생 로직 없음.
- **프롬프트에서만 정해지는 사건:** `SCENE_BRIEFS[2]` — "책과 파란 천 책갈피가 드러난다. 책 제목은 《조금 늦은 안부》." 순수 텍스트.
- **UI가 가정하고 있는 사건:** 없음.
- **생성 이미지가 가정하고 있는 상황:** `SCENE_PROMPTS[2]` — "책을 들고 건네는 자세"가 대화 진행과 무관하게 고정 이미지로 나온다(플레이어가 아직 book_given 이벤트를 발생시키지 않았어도 이 장면 이미지는 항상 "건네는 자세"로 그려짐 — **이미지가 실제 대화 상태를 반영하지 않는다는 근거**, 6장 참고).
- **상태 변수 변경:** `book_owner`, `bookmark_owner`(seoyun→player 가능해지는 게이트가 열림).
- **다음 장면으로 넘겨야 하는 데이터:** 없음(위와 동일 이유).

## Scene 3 (쓰지 못한 한 문장 / 창가 작은 탁자, 턴 7~9)

- **코드상 반드시 발생하는 사건:** **카드 가용성**. `is_card_available()`(`api/common.py`)이 `session.scene_id >= 3 and not card.decided`일 때만 `card_available: true`를 반환 — 이는 프론트가 카드 작성 UI를 보여줄지 결정하는 유일한 신호이므로, 장면3 진입이 카드 UI 노출의 실제 게이트다(문서상 서사와 일치하지만 코드로 강제되는 몇 안 되는 장면별 조건 중 하나).
- **프롬프트에서만 정해지는 사건:** `SCENE_BRIEFS[3]` — "빈 카드에 남길 말을 고른다"는 텍스트 지시. 카드 자체의 존재는 코드가 강제하지만("장면3부터 API가 카드 제출을 받아준다"), 카드 관련 **대화**를 LLM이 자연스럽게 이끄는지는 순수 프롬프트 영역.
- **UI가 가정하고 있는 사건:** 카드 편집기 노출(ui-spec.md 7장) — `card_available` 필드에 의존.
- **생성 이미지가 가정하고 있는 상황:** `SCENE_PROMPTS[3]` — "빈 카드와 은색 펜이 놓인 자세"가 고정.
- **상태 변수 변경:** `Card.decided/written/text/author/owner/decided_turn` (카드 전용 API `POST /card`를 통해서만 변경 가능, 일반 턴 API로는 카드 상태를 못 바꿈).
- **다음 장면으로 넘겨야 하는 데이터:** 없음.

## Scene 4 (문을 닫기 전에 / 출입문 밖 처마 아래, 턴 10~12)

- **코드상 반드시 발생하는 사건:** **턴 12 완료 시 `door_locked = True`와 엔딩 확정이 무조건 발생**(`_finalize_turn12`, `app/api/turns.py`). 이것이 이 게임에서 유일하게 "장면 진행과 무관하게 특정 턴 번호에 100% 강제 실행되는 상태 변화"다. LLM 제안 여부와 무관하게 서버가 직접 `session.door_locked = True`와 `ConfirmedEvent(event_type="door_locked")`를 만든다(engine/state.py의 허용목록 검증 로직조차 거치지 않고 `turns.py`가 직접 씀 — 유일한 예외 경로).
- **프롬프트에서만 정해지는 사건:** `SCENE_BRIEFS[4]` — "조명을 끄고 문을 잠근다. 마지막 응답은 새 질문으로 끝내지 않는다"는 텍스트 지시(마지막 응답 형식 자체는 강제되지 않음, LLM이 안 따라도 코드는 감지 안 함).
- **UI가 가정하고 있는 사건:** 11턴 완료 시 "마지막 입력 안내"(ui-spec.md 6장 표) — 이는 순수 프론트 표시 로직으로, 서버는 `completed_turns`와 `is_final_turn`만 준다. 프론트가 "11이면 안내 문구"를 직접 판단해야 한다(서버가 전용 플래그를 주지 않음 — 프론트 하드코딩 영역).
- **생성 이미지가 가정하고 있는 상황:** `SCENE_PROMPTS[4]` — "열쇠를 든 채 문 밖에서 돌아보는 자세"가 고정. 엔딩 이미지의 `_LOCATION_BY_SCENE[4]`도 별도로 "문이 잠긴 채"를 전제.
- **상태 변수 변경:** `door_locked`(강제), 그 외 이벤트(`contact_exchanged`, `future_plan_accepted`, `player_departed`)는 자유.
- **다음 장면으로 넘겨야 하는 데이터:** 없음(마지막 장면이라 전달 대상 없음, 곧바로 엔딩 생성으로 이어짐).

### "책 → 책갈피 → 카드 → 문 잠금" 흐름 결합도 요약

| 오브젝트 | 텍스트(프롬프트)에만 존재 | 코드가 실제로 기대 | DB/state schema 보유 | 이미지 프롬프트가 기대 | 엔딩 생성기가 기대 |
|---|---|---|---|---|---|
| 책 | 예(제목·소재) | 아니오(강제 발생 로직 없음) | 예(`book_owner`) | 예(장면2, 엔딩 props) | 예(props 분기) |
| 책갈피 | 예 | 아니오 | 예(`bookmark_owner`) | 아니오(엔딩 슬롯엔 책갈피 전용 분기 없음 — book_owner/bookmark_owner를 OR로만 씀, `expression` 계산에서) | 예(`expression` 계산에서 `bookmark_owner`도 체크) |
| 카드 | 예 | **예**(전용 테이블+API+`card_available` 게이트) | 예(전용 `Card` 테이블) | 예(장면3 이미지, 엔딩 props "Holding the written card") | 예(엔딩 응답의 전용 `card` 필드 + props 분기) |
| 문 잠금 | 예 | **예**(턴12에 무조건 강제 설정, 유일하게 검증 없이 직접 세팅) | 예(`door_locked` bool) | 예(장면4, 엔딩 posture) | 예(posture 분기) |

**결론:** 책·책갈피는 순수 소프트 상태(코드가 강제로 발생시키지 않음, 발생 안 해도 아무 데도 안 걸림)라 이름과 서사적 의미를 통째로 갈아끼우기 쉽다. **카드와 문 잠금은 구조적으로 훨씬 깊게 박혀 있다** — 카드는 전용 테이블/API/UI가 있고, 문 잠금은 유일하게 "허용목록 검증 없이 서버가 직접 강제하는 상태"라서 "턴12 완료 시 반드시 확정되는 사건"이라는 **역할**은 다른 이름의 사건으로 바꾸더라도 반드시 유지해야 한다(단, "문을 잠근다"는 텍스트 자체는 얼마든지 다른 사건으로 교체 가능 — 예: "마지막 조명을 끈다" 등. 역할(턴12 강제 확정 플래그)만 유지하면 됨).

---

# 4. 스토리와 코드가 연결되는 모든 상태값

**근거:** `backend/app/models.py`(Session 컬럼), `backend/app/engine/state.py`(APPLIERS/RECORD_TEMPLATES), `backend/app/engine/ending.py`(엔딩 슬롯 계산)

| 상태값 | 용도 | 어느 장면에서 변경 | 엔딩에 사용 | 스토리 변경 시 유지 필요 여부 |
|---|---|---|---|---|
| `scene_id` | 현재 장면(1~4) | 서버가 턴 완료 시 자동(모든 장면) | 예(`_LOCATION_BY_SCENE`) | **필수**(구조 자체, 값 의미는 자유) |
| `completed_turns` | 진행 턴 수 | 매 턴 | 아니오(직접 사용 안 함, `is_final_turn` 계산에만) | **필수** |
| `story_time` | 표시용 이야기 시각 | 매 턴 | 아니오 | 선택(표시용, 없애도 로직 안 깨짐 — 단 UI 텍스트라 스토리 톤엔 영향) |
| `trust`/`closeness`/`tension` | (설계상)관계 수치 | 어디서도 갱신 안 함(디폴트값 고정) | 아니오 | **불필요(사실상 죽은 코드)** — 자유롭게 제거/대체 가능 |
| `help_status` | 정리 돕기 진행 상태(not_offered/offered/helped) | 전 장면(제약 없음) | 아니오(evidence 목록엔 `help_completed`만 사용) | 선택 — 다른 "돕기 유형 상태"로 교체 가능 |
| `book_owner` | 책 소유(seoyun/player) | 장면2 이상에서만 유효 | 예(props, evidence) | 선택 — 이름·의미 교체 가능, "소유권 이진 상태" 패턴 자체는 재사용 권장 |
| `bookmark_owner` | 책갈피 소유 | 장면2 이상 | 예(expression 계산에 포함) | 선택 |
| `future_plan` | 제안된 약속 텍스트(자유 텍스트 저장) | 전 장면 | 아니오(직접 노출 안 하지만 confirmed_state_summary로 LLM엔 전달) | 선택 — "제안" 슬롯 자체는 재사용 가능 |
| `future_plan_accepted` | 약속이 실제 합의됐는가 | 전 장면(제안 이후) | 예(expression 분기) | 선택 — "제안→합의 2단계" 패턴은 story.md 8.3 규칙 구현이라 유지 권장 |
| `contact_exchanged` | 연락처 교환 여부 | 전 장면 | 예(expression, evidence) | 선택 |
| `player_present` | 문 잠글 때 플레이어가 자리에 있는가 | `player_departed` 이벤트로만 false | 예(distance 계산) | 선택 — 다만 "조기 이탈"이라는 서사 장치 자체는 story.md 7.3(이탈 상황)과 결합돼 있어 완전히 없애면 그 절도 재검토 필요 |
| `door_locked` | 문 잠금 확정 여부 | **턴12에서만, 서버가 강제** | 예(posture 계산) | 3장 결론 참고 — 역할 유지 권장 |
| `ended_early` | 조기 종료 여부 | `POST /end` 호출 시 | 간접(status로 분기, 슬롯 계산엔 직접 안 씀) | 필수(조기 종료 기능을 유지한다면) |
| `card.decided/written/text/author/owner/decided_turn` | 카드 상태 전체 | 장면3 이상, 전용 API로만 | 예(전용 `card` 필드 + props) | **필수**(카드 기능 자체를 유지한다면 구조 그대로 필요) |
| `ending_title/body/unresolved/evidence` | 확정된 엔딩 결과 캐시 | 엔딩 확정 시 1회 | 자기 자신(엔딩 응답으로 그대로 나감) | 필수(엔딩 재생성 방지 캐시 역할) |
| `ending_image_id`/`portrait_image_id` | 이미지 참조 | 각각의 생성 시점 | 예 | 필수(이미지 구조 유지 시) |

**LLM이 실제로 제안할 수 있는 이벤트 타입(=proposed_events 허용목록, `llm/prompts.py: ALLOWED_EVENT_TYPES` = `engine/state.py: APPLIERS`의 키)은 정확히 9개**: `help_offered, help_completed, book_given, book_declined, bookmark_given, future_plan_proposed, future_plan_accepted, contact_exchanged, player_departed`. 새 스토리에서 다른 사건(예: "함께 사진을 찍는다", "노래를 틀어준다")을 상태로 확정하고 싶다면 **이 허용목록에 새 이벤트 타입과 `APPLIERS` 함수를 추가하는 코드 작업이 필요**하다(이건 "스토리만 바꾸면 되는" 영역이 아니라 B급 코드 변경 — 새 event_type 문자열을 프롬프트에 추가하는 것만으로는 실제로 상태가 안 바뀐다. `engine/state.py`에 대응 함수가 없으면 LLM이 제안해도 조용히 버려짐, `confirm_proposed_events`의 `if applier is None: continue`).

---

# 5. LLM 프롬프트 구조

**조립 파일:** `backend/app/llm/prompts.py`(전부), 호출부 `backend/app/llm/client.py`

- **system prompt 전체 조립 순서**(`build_system_prompt`): `PERSONA_YAML`(고정 캐릭터 설정) → `SCENARIO_YAML`(고정 시나리오 메타) → `SCENE_BRIEFS[현재 scene_id]`(장면별 목적·고정사건) → `confirmed_state_summary()`(현재 확정 상태 요약, 매 턴 동적 생성) → `FORBIDDEN_NOTES`(금지사항, 고정 리스트) → `GUIDANCE_NOTES`(대화 진행 지침, 고정 리스트) → `RESPONSE_FORMAT_NOTE`(JSON 스키마+허용 이벤트 타입 안내). 이 6개 블록을 `\n\n`으로 join.
- **persona:** `PERSONA_YAML` 하나의 문자열 상수. 캐릭터명/나이/역할/성격/말투/가치관/현재목표/숨겨진사실/경계선을 전부 담은 YAML 텍스트 블록. **스토리 재설계 시 이 블록만 다시 쓰면 캐릭터 설정 변경의 90%가 끝난다.**
- **scenario:** `SCENARIO_YAML` — 시간창·최대턴·장면당턴수·장면공간 이름·고정 beat 목록. **이 블록의 숫자(max_turns, scene_turns)는 실제 로직(`scene.py`)과 별개의 텍스트라 여기만 바꾸고 `scene.py`를 안 바꾸면 LLM에게 주는 정보와 실제 서버 동작이 어긋난다** — 둘을 항상 같이 고쳐야 함(이 동기화가 코드로 강제되지 않는 취약점).
- **현재 scene:** `SCENE_BRIEFS[session.scene_id]` 하나만 삽입(4개 중 현재 것만, 전체 스토리라인은 LLM에게 안 보여줌 — 매 턴 자기 장면 브리핑만 봄).
- **현재 turn:** system prompt에 턴 번호 자체는 안 들어간다(단, `confirmed_state_summary`에도 없음). LLM은 몇 턴째인지 명시적으로 모른다 — 오직 대화 히스토리 길이와 장면 브리핑으로 유추.
- **이전 대화(history):** `build_history_messages` — 최근 8턴(`get_recent_messages`의 `max_turns=8` 기본값, `api/common.py`)을 OpenAI chat 메시지 role로 변환. `record` 종류 메시지(시스템 기록 카드)는 히스토리에서 제외됨.
- **memory/state:** `confirmed_state_summary()` — help_status, book_owner, bookmark_owner, future_plan(+수락여부), contact_exchanged, player_present, card 상태를 사람이 읽는 한국어 문장으로 요약해 매 턴 새로 만든다. **여기 나열된 필드 목록이 4장 상태값 표와 정확히 일치** — 새 상태값을 추가하면 이 함수에도 줄을 추가해야 LLM이 인지한다.
- **fixed events:** `SCENARIO_YAML`의 `fixed_beats` 리스트(텍스트) + 각 `SCENE_BRIEFS`의 "고정 사건" 문장. 코드가 이걸 검증하지는 않는다(순수 지시).
- **hidden facts:** `PERSONA_YAML`의 `hidden_facts` 리스트. LLM에게는 항상 보이고(시스템 프롬프트 전체 삽입), 언제 공개할지는 LLM 재량.
- **장면 목표:** 각 `SCENE_BRIEFS[n]`의 "목적:" 줄.
- **다음 장면 강제 진행 조건:** 프롬프트에는 조건이 없다. 장면 전환은 100% 서버가 턴 번호로 강제하므로 LLM에게 "언제 넘어가라"고 지시할 필요 자체가 없는 구조(전환 자체를 LLM이 판단하지 않음).
- **캐릭터 반응 규칙:** `FORBIDDEN_NOTES`(7개 항목: 외형 언급 금지, 세계상태 임의 확정 금지, 글자수 제약, 질문으로만 끝내지 않기, 이미 등장한 사물 재발견처럼 쓰지 않기, 비극적 사연 금지, 폐업 반전 금지) + `GUIDANCE_NOTES`(4개 항목: 대화가 막히지 않게 여지 남기기 등, 최근에 피드백으로 추가된 것).
- **엔딩 생성 prompt:** 별도 함수 `build_ending_system_prompt` — `PERSONA_YAML` + (확정상태 요약 + 문잠글때 플레이어 존재여부 + evidence로 뽑힌 실제 대화 원문 목록) + `ENDING_FORBIDDEN_NOTES`(7개, 턴 생성과는 다른 별도 리스트 — 예: "8~20자 제목", "350~550자 본문", "1년 뒤 결혼 확정 금지") + `ENDING_RESPONSE_FORMAT_NOTE`. **턴 대화 프롬프트와 완전히 분리된 별도 시스템**(대화 히스토리를 거의 안 주고 evidence 인용문만 줌 — LLM이 엔딩을 쓸 때 전체 대화 로그를 못 본다는 뜻, `messages`가 아니라 quotes만 참조).

**스토리 재설계 시 수정해야 할 파일 우선순위:**
1. `llm/prompts.py`의 `PERSONA_YAML`, `SCENARIO_YAML`, `SCENE_BRIEFS`, `FORBIDDEN_NOTES`, `GUIDANCE_NOTES`, `ENDING_FORBIDDEN_NOTES` — 전부 텍스트 상수 수정만으로 스토리 내용의 대부분을 바꿀 수 있다.
2. 새 이벤트 타입이 필요하면 `engine/state.py`의 `APPLIERS`/`RECORD_TEMPLATES`, `llm/prompts.py`의 `ALLOWED_EVENT_TYPES`, `engine/ending.py`의 `EVIDENCE_EFFECT_TEXT`, `confirmed_state_summary` 4곳을 동시에 고쳐야 한다(코드 수정, B급).
3. 장면 수·턴 수를 바꾸면 `engine/scene.py`의 `SCENES`/`_TURN_TABLE`/`_TRANSITIONS_AFTER`도 함께.

---

# 6. 이미지 생성과 스토리의 결합

**근거:** `backend/app/images/prompts.py`, `backend/app/images/presets.py`, `backend/app/api/sessions.py`, `backend/app/api/turns.py`, `backend/app/engine/ending.py`, CLAUDE.md 9장(설정값 확인용, 코드와 대조)

- **총 몇 장:** 정확히 6장 고정 — 초상화 1 + 장면 4(SCENES 개수만큼) + 엔딩 1. 장면 이미지 개수는 `SCENES` 딕셔너리 크기에 종속(장면 수를 바꾸면 이미지 수도 자동으로 따라감).
- **언제 생성되는가:**
  - 초상화: `create_session`(또는 `retry_portrait`) 안에서 **동기** 호출(`generate_portrait`). 실패해도 세션 row는 만들어지고 `portrait_image_id`만 비어 실패 상태로 남는다.
  - 장면 1~4: 초상화 성공 **직후** `background_tasks.add_task(_run_background_scene_jobs, ...)`로 즉시 시작(회차 생성 시점부터, `/start` 호출을 기다리지 않음 — CLAUDE.md 9.3 문서의 "장면1은 동기, 2~4는 백그라운드"는 **문서 vs 실제 차이**: 실제 코드는 장면 1도 백그라운드다. 이 변경은 이미 이전 세션에서 사용자 피드백 대응으로 반영됐고 `docs/api-contract.md`에는 "장면1도 예외 없이 같은 스켈레톤+폴링 패턴"으로 갱신돼 있어 api-contract.md가 최신, CLAUDE.md 9.3 표는 갱신 누락 상태).
  - 엔딩: 턴12 완료 또는 조기종료 시 `finalize_ending_text`(텍스트, 동기) 직후 `background_tasks.add_task(_run_ending_image_job, ...)`(이미지, 비동기).
- **Scene별 이미지가 고정되어 있는가:** **예, 완전히 고정.** `SCENE_PROMPTS[scene_id]`는 세션 상태나 대화 내용을 전혀 참조하지 않는 정적 딕셔너리. 같은 장면이면 어떤 대화를 했든 항상 동일한 이미지 프롬프트가 나간다(참조 이미지=초상화만 세션마다 다르므로 인물 외형만 다르고 포즈·구도·소품은 항상 같음).
- **이미지 프롬프트가 Scene 번호에 의존하는가:** 예. `scene_prompt(scene_id)`가 `SCENE_PROMPTS[scene_id]`를 정수 키로 직접 조회 — 장면 번호가 이미지 프롬프트 선택의 유일한 입력.
- **장소가 고정되어 있는가:** 예(위 2·3장 참고).
- **소품(책/책갈피/카드/문 등)이 코드에 하드코딩돼 있는가:** 예, 전부 영문 텍스트로 하드코딩(`SCENE_PROMPTS`, `_ENDING_TEMPLATE` 슬롯 값들인 `_LOCATION_BY_SCENE`, `compute_ending_slots`의 posture/expression/props/distance 영문 조각). 이 값들은 프로그램 로직이 아니라 순수 문자열이라 교체 자체는 쉽지만(C~B), **엔딩 이미지만은 상태값 조합에 따라 동적으로 슬롯이 선택**된다는 점이 장면 이미지와 다르다(장면 이미지는 완전 정적, 엔딩 이미지만 상태 반영).
- **대화 결과가 이미지 프롬프트에 어느 정도 반영되는가:** **장면 이미지(1~4)는 전혀 반영 안 됨(0%).** 오직 **엔딩 이미지 1장만** `compute_ending_slots()`를 통해 5개 상태값(door_locked, future_plan_accepted, contact_exchanged, book_owner, bookmark_owner, card.written, player_present)의 조합으로 5개 슬롯(location/posture/expression/props/distance) 문구가 결정된다. 이것이 CLAUDE.md 5.5("사용자 입력은 이미지 프롬프트에 닿지 않는다")의 실제 구현 — 대화 원문이 아니라 **서버가 검증한 상태값**만 슬롯을 통해 간접 반영됨.
- **엔딩 이미지는 어떤 state를 입력받는가:** `engine/ending.py: compute_ending_slots(session, card)` 함수 시그니처가 정확한 답 — `session.scene_id`(location), `session.door_locked`(posture), `session.future_plan_accepted`/`contact_exchanged`/`book_owner`/`bookmark_owner`(expression), `card.written`/`session.book_owner`(props), `session.player_present`(distance). 이 5개 계산 분기가 곧 "엔딩 이미지가 실제로 반영하는 스토리 사건의 전부"다.
- **스토리 사건을 바꿀 경우 이미지 쪽에서 같이 수정해야 하는 파일:** `images/prompts.py`(SCENE_PROMPTS, `_CHARACTER_TEMPLATE`, `_ENDING_TEMPLATE`가 참조하는 슬롯 이름), `engine/ending.py`(compute_ending_slots의 분기 로직 자체 — 새 상태값을 반영하려면 이 함수의 if/elif를 새로 써야 함, 텍스트 교체가 아니라 로직 수정이라 B급).

---

# 7. UI와 스토리의 결합

**근거:** `docs/ui-spec.md`, `docs/api-contract.md`, 및 백엔드가 실제로 내려주는 필드(`schemas.py`)

- **장면 제목 표시:** 서버가 `scene.name`으로 문자열을 내려줌(`SCENES[id]["name"]`) — UI는 하드코딩 없이 그대로 표시. 장면 이름을 바꿔도 UI 코드 수정 불필요.
- **시간 표시:** 서버가 `story_time` 문자열(`"20:41"` 형식)로 내려줌. UI는 진행 막대 계산에 `20:30~21:00` 범위를 하드코딩(ui-spec.md 5.2 "20:30~21:00 범위의 얇은 진행 막대") — **시간대 자체를 바꾸면 프론트의 진행 막대 범위 상수도 같이 고쳐야 함**(백엔드 API 계약엔 이 범위가 필드로 없음 — 프론트 전용 하드코딩 가능성 높음, 실제 프론트 코드는 이번 조사 범위 밖).
- **장면 구분선:** `card_available`/`scene.entered`(턴 응답의 `scene.entered`가 true인 순간에만 프론트가 구분선을 1회 렌더)로 트리거. 장면 이름이 바뀌어도 이 로직은 안 깨짐.
- **진행률/남은 턴:** `completed_turns`/`is_final_turn`이 숫자·불리언으로 내려감 — 턴 수를 바꿔도 API 필드 자체는 안 바뀜(값만 달라짐). UI가 "12"를 하드코딩했는지는 프론트 코드 확인 필요(백엔드 범위 밖).
- **카드 작성 UI:** `card_available`(불리언)에 완전히 의존. 카드 기능을 유지하는 한 이 흐름은 안 깨짐. 카드 자체를 없애면 `EndingResponse.card` 필드, `POST /card` 엔드포인트, `card_available` 로직을 프론트에서도 전부 제거해야 함(API 계약 변경, 양쪽 다 수정).
- **카드 글자수 제한(80자):** 서버(`CARD_MAX_VISIBLE_CHARS`)와 프론트가 각각 독립적으로 제한을 걸어야 함(`docs/ops-notes.md`/이전 worklog에 "그래프클러스터 vs 코드포인트 불일치" 이슈가 언급돼 있어 완전히 서버-프론트 동기화된 상태는 아님 — 미해결 이슈로 남아있음, 이번 조사에서 재확인).
- **책/책갈피 관련 UI:** 전용 컴포넌트 없음 — 대화 메시지(`kind: "record"`)로만 표현됨. 즉 "책", "책갈피"는 UI 레벨에서 특별 취급되지 않고 시스템 기록 카드(ui-spec.md 5.3의 "기억에 남을 순간" 라벨)로만 보인다. **UI가 책/책갈피라는 개념 자체를 하드코딩하지 않으므로 이름과 서사를 바꿔도 UI가 깨지지 않는다.**
- **엔딩 화면:** `EndingResponse`의 `title/body/card/evidence/unresolved/image` 6개 필드에 정확히 대응하는 6개 UI 섹션(ui-spec.md 8.1)이 있다. 이 6개 필드 구조 자체를 바꾸면(예: evidence 개수 상한을 바꾸거나 필드를 추가/제거) API 계약과 양쪽 UI를 함께 수정해야 함.
- **기억 회수/원문 인용(`evidence`):** `MAX_EVIDENCE = 3`(engine/ending.py 상수) — UI는 "2~3개 카드가 순차 등장"(ui-spec.md 8.2)한다고 돼 있어 서버 상수와 문서 숫자가 대략 일치. evidence는 `EVIDENCE_EFFECT_TEXT`에 있는 이벤트 타입에서만 나오므로, **엔딩에서 "근거로 회수되는 사건"은 이벤트 타입 5개(book_given/bookmark_given/future_plan_accepted/contact_exchanged/help_completed)로 제한된다** — 여기 없는 이벤트(help_offered, book_declined, player_departed 등)는 확정돼도 절대 엔딩 근거 카드로 안 뜬다. 새 이벤트를 근거로 쓰려면 이 딕셔너리에 추가해야 함(B급).
- **소품 표시:** 위와 동일(전용 UI 없음, 텍스트로만).
- **이미지 위치:** 좌측 480px 고정 컬럼(ui-spec.md 2.1) — 장면 수·이미지 세로 비율(1024×1536)에 의존. 이미지 종횡비를 바꾸면 레이아웃 상수도 같이 조정 필요(스토리 내용과는 무관, 순수 에셋 스펙).
- **마지막 턴 안내:** 서버 필드 없이 프론트가 `completed_turns === 11`을 직접 판단하는 것으로 보인다(ui-spec.md 6장 표에 "11 → 마지막 입력 안내"라고만 돼 있고 API 계약에 별도 플래그 없음) — **턴 수를 바꾸면 이 하드코딩된 조건도 프론트에서 같이 고쳐야 함**(백엔드가 전용 플래그를 안 주는 게 잠재적 결합 지점).

**결론(7장):** UI는 대체로 "책", "책갈피", "카드", "문 잠금" 같은 구체적 서사 명칭을 컴포넌트 레벨에서 하드코딩하지 않고, 서버가 준 텍스트(`scene.name`, 메시지 텍스트, `record` 카드 라벨)를 그대로 보여주는 방식이라 **서사 내용 교체에는 매우 안전**하다. 유일하게 구조적으로 UI와 강결합된 것은 카드(전용 필드/엔드포인트)와 턴 수(11/12 같은 숫자를 프론트가 자체적으로 하드코딩했을 가능성 — 정확한 위치는 `frontend/` 코드 확인 필요, 이번 조사는 백엔드 기준이라 프론트 실제 코드는 못 봄).

---

# 8. 내가 가장 알고 싶은 것

### Q1. 4장면×3턴=12턴 구조를 유지하면서, 각 장면의 스토리 사건 자체를 완전히 새로 설계할 수 있는가?

**가능하다. 그것도 상당히 자유롭게.** 장면 전환은 순수하게 턴 번호로 결정되고(2장), 장면별 "고정 사건"은 전부 `llm/prompts.py`의 `SCENE_BRIEFS` 텍스트일 뿐 코드가 검증하지 않는다(3장). 유일하게 코드가 실제로 강제하는 것은:
- 장면3 이상부터 카드 UI가 열린다는 게이트(`is_card_available`)
- 턴12에 `door_locked`(또는 이름을 바꾼 동일 역할의 플래그)가 무조건 확정된다는 것

이 두 가지 **역할**(카드라는 소품/UI 자체, 마지막 턴 강제 확정 사건)만 유지하면, 그 안의 구체적 내용(무엇을 발견하고, 무엇을 대화하고, 어떤 사건이 일어나는지)은 프롬프트 텍스트 교체만으로 완전히 새로 설계할 수 있다. 새로운 상태값(예: "함께 사진을 찍는다")을 서버가 확정하게 하려면 `engine/state.py`에 함수 하나를 추가하는 코드 작업이 필요하지만, 이것도 기존 9개 함수와 동일한 패턴을 복사하는 수준이라 비용이 크지 않다.

### Q2. 책 → 책갈피 → 카드 → 문 잠금 중 무엇이 구현상 필수이고 무엇은 교체 가능한가?

- **책, 책갈피:** 완전히 교체 가능(C~B급). 소유권 이진 상태 컬럼 2개(`book_owner`, `bookmark_owner`)만 재사용하거나, 아예 이름을 바꿔도(예: "선물"→다른 개념) 로직이 그대로 성립한다. 코드가 강제로 발생시키지 않으므로(플레이어가 유도 안 하면 영원히 안 일어나도 됨) 서사적 비중을 낮추거나 아예 다른 소품으로 완전 대체 가능.
- **카드:** 교체 어려움(A급). 전용 테이블·API·UI가 있어 "빈 카드에 한 문장을 남긴다"는 **인터랙션 형식** 자체를 없애거나 완전히 다른 형식(예: 그림을 그린다, 노래를 고른다)으로 바꾸려면 백엔드 API와 프론트 컴포넌트를 재설계해야 한다. 다만 "카드에 무엇을 쓰는가"의 **서사적 맥락**(왜 카드가 있는지, 무엇을 상징하는지)은 완전히 자유.
- **문 잠금:** 텍스트는 교체 가능하지만 **역할**(턴12 완료 시 서버가 무조건 확정하는 유일한 상태 플래그)은 유지를 권장. 이걸 없애면 엔딩 이미지 posture 계산(`compute_ending_slots`)의 분기 하나가 근거를 잃는다(다른 근거로 대체하는 코드 수정 필요).

### Q3. "폐점하는 서점에서 단골과 마지막 30분을 보낸다"라는 큰 설정 자체도 바꿀 수 있는가?

**설정 텍스트 자체는 바꿀 수 있지만(B급), 그 설정이 만들어내는 몇 가지 "형식적 성질"은 코드/이미지에 이미 스며들어 있다.**

- 장소가 "제한된 한 공간의 서로 다른 네 구역"이라는 형식(장면마다 다른 서브 공간)은 이미지 프롬프트 세트 구조(`SCENE_PROMPTS`, 로케이션별 조명·톤)에 반영돼 있다. 완전히 다른 배경(예: 여러 도시를 돌아다니는 이야기)으로 바꾸면 이 "한 공간, 네 구역"이라는 이미지 연출 전제를 재설계해야 한다.
- "시간제한(30분)"이라는 형식은 story.md의 서사적 장치일 뿐 코드가 실시간으로 강제하지 않는다(ui-spec.md 6장 "실제 15분을 넘겨도 강제 종료하지 않는다") — 순수 텍스트/연출 장치라 자유롭게 바꿔도 로직에 영향 없음.
- "의상 고정"(니트+앞치마)은 이미지 CHARACTER 템플릿에 하드코딩(`_CHARACTER_TEMPLATE`)돼 있어 배경 설정(서점)과 강하게 묶여 있다. 배경을 바꾸면 이 의상 서술도 같이 바꿔야 자연스럽다.
- 결론: **장소·시간·폐점이라는 서사 자체는 UI/코드에 이름으로 하드코딩돼 있지 않다**(2장 표 참고, "책방"이라는 문자열은 프롬프트에만 있음). 그러나 "하나의 고정 공간을 네 구역으로 나눠 이미지 연출을 다르게 한다"는 **형식**은 이미지 파이프라인과 강하게 결합돼 있어, 이 형식 자체(공간 1개, 서브구역 4개)를 유지하는 선에서 배경을 바꾸는 것이 비용이 가장 낮다.

### Q4. 캐릭터 한서윤의 성격/배경/관계/숨겨진 사실/현재 목표를 바꾸면 코드 수정이 필요한가, 프롬프트 수정만 필요한가?

**프롬프트 수정만으로 충분하다.** `PERSONA_YAML`(`llm/prompts.py`)은 순수 문자열이고 코드가 이 안의 개별 필드를 파싱하거나 조건 분기에 쓰지 않는다(YAML처럼 보이지만 실제로는 파싱되지 않고 그대로 LLM에게 전달되는 텍스트 블록). 단, 예외 2가지:
1. **나이·성별**을 바꾸면 이미지 CHARACTER 템플릿(`images/prompts.py`의 `_CHARACTER_TEMPLATE` — "A 27-year-old Korean woman")도 별도로 고쳐야 한다(프롬프트지만 다른 파일).
2. **캐릭터 이름(한서윤)** 자체는 이미지 프롬프트에는 전혀 등장하지 않는다(CLAUDE.md 5.5/7.3 원칙대로 외형 이미지는 이름 없이 인상착의로만 서술) — 이름은 오직 대화 프롬프트(PERSONA_YAML)와 DB에 없는 프론트 표시용 텍스트에만 존재. 이름을 바꾸는 것은 완전히 자유(코드 영향 없음).

### Q5. 현재 구현을 최대한 안 건드린다는 조건에서, 스토리 디자이너가 자유롭게 바꿀 수 있는 영역은?

- 캐릭터 이름/성격/배경/말투/숨겨진 사실/현재 목표 (`PERSONA_YAML` 전체)
- 시나리오 개요 텍스트(`SCENARIO_YAML`의 서술 부분, 숫자는 `scene.py`와 동기화 필요)
- 4개 장면 각각의 목적·고정사건 서술(`SCENE_BRIEFS`)
- 대화 금지사항/진행지침의 구체적 문구(`FORBIDDEN_NOTES`, `GUIDANCE_NOTES`) — 다만 "외형 언급 금지", "세계상태 임의확정 금지" 같은 **구조적 원칙 문구**는 유지 권장(이미지 일관성·서버 권위 원칙과 직결)
- 엔딩 문체 규칙(`ENDING_FORBIDDEN_NOTES`)
- 오프닝 고정 대사 4줄(`engine/opening.py`)
- 장소·소품의 구체적 이름과 영문 이미지 묘사(`images/prompts.py`의 모든 텍스트 블록) — 단 "네 공간, 인물 1인, 세로구도" 같은 형식은 유지 권장
- 외형 프리셋 라벨/조각(`images/presets.py`) — 7축 구조 자체를 유지한다면 각 축의 선택지 내용은 자유
- 카드에 "무엇을 쓰는가"의 서사적 의미, 문잠금을 대체하는 사건의 텍스트(단 역할은 유지)
- 책/책갈피를 완전히 다른 소품/사건으로 교체

이 모두가 **코드 재배포는 필요하지만(정적 문자열 상수 수정), DB 마이그레이션이나 API 계약 변경은 필요 없다.**

---

# 스토리 리디자인 제약사항

## 반드시 유지하는 것을 권장
- 4장면 / 12턴(3턴×4장면) 구조, 턴 기반 강제 전환 (`engine/scene.py`)
- "LLM 제안 → 서버 허용목록 검증 후 확정" 상태 전이 원칙 (`engine/state.py`)
- 카드(빈 카드에 한 문장 남기기) 인터랙션의 구조(전용 API/테이블/UI 게이트)
- 턴12 완료 시 서버가 강제로 확정하는 "마지막 사건" 플래그 1개(현재 `door_locked`) — 역할 유지, 이름·서사는 자유
- 캐릭터 1명, 참조 이미지 1장(초상화)만 사용하는 이미지 파이프라인
- 회차당 이미지 6장(초상화1+장면4+엔딩1), 엔딩 이미지만 상태값 기반 동적 슬롯을 갖는 구조
- 외형 7축 프리셋 시스템의 구조(축 개수는 유지, 각 축 내용은 자유)

## 유지하면 좋지만 변경 가능
- 장면당 턴 수(3턴 고정 → ui-spec.md에 이미 "4번째 장면만 4턴" 대안이 문서화돼 있어 균등 분배가 필수는 아님)
- 총 턴 수(12) 자체 — API 계약이 숫자를 하드코딩해 노출하지 않아 서버만 바꿔도 됨(프론트 하드코딩 여부는 별도 확인 필요)
- 장소(서점)와 그에 따른 의상 고정 — 다른 배경으로 바꾸되 "한 공간, 네 서브구역" 형식은 유지 시 비용 최소
- 책/책갈피의 서사적 정체성(소유권 이진 상태 구조는 재사용 권장)
- 관계 상태값 목록(9개 이벤트 타입) — 새 이벤트 추가는 B급 코드 작업(패턴 복사 수준)

## 자유롭게 변경 가능
- 캐릭터 이름/성격/배경/말투/숨겨진 사실/목표 (`PERSONA_YAML`)
- 장면별 서사 내용, 목적, 고정 사건의 구체적 서술 (`SCENE_BRIEFS`)
- 이미지 프롬프트의 구체적 장면 묘사, 소품, 조명 서술 (`images/prompts.py`)
- 외형 프리셋의 라벨/조각 내용 (`images/presets.py`)
- 오프닝 대사 (`engine/opening.py`)
- 엔딩 문체·분량 규칙 (`ENDING_FORBIDDEN_NOTES`)
- trust/closeness/tension 수치(현재 완전히 미사용 — 자유 활용/삭제)
- 장면별 이야기 시각 표시값(`_TURN_TABLE`의 시각 문자열)

## 변경하면 코드 수정 필요
- 항목: 장면 개수 변경
  - 관련 파일: `backend/app/engine/scene.py`(SCENES/_TURN_TABLE/_TRANSITIONS_AFTER), `backend/app/images/prompts.py`(SCENE_PROMPTS), `backend/app/engine/ending.py`(_LOCATION_BY_SCENE), 프론트 장면 배열
  - 수정 범위: 4개 파일, 각각 딕셔너리 키 추가/삭제 수준
  - 예상 영향: 회차당 이미지 개수(현재 6장)도 자동 변경됨
- 항목: 새로운 상태 확정 이벤트 타입 추가(예: 새로운 소품/행동)
  - 관련 파일: `backend/app/engine/state.py`(APPLIERS, RECORD_TEMPLATES), `backend/app/llm/prompts.py`(ALLOWED_EVENT_TYPES), `backend/app/engine/ending.py`(EVIDENCE_EFFECT_TEXT, confirmed_state_summary 호출부는 prompts.py에 있음)
  - 수정 범위: 함수 1개 추가(기존 9개 함수와 동일 패턴 복사) + 딕셔너리 3곳에 항목 추가
  - 예상 영향: 새 이벤트가 엔딩 근거(evidence)로도 뜨게 하려면 EVIDENCE_EFFECT_TEXT에도 추가해야 함, 안 하면 확정은 되지만 엔딩 인용에는 안 나옴
- 항목: 카드 인터랙션 형식 자체를 바꿈(다른 형태의 소품/행동으로 교체)
  - 관련 파일: `backend/app/models.py`(Card 테이블), `backend/app/api/card.py`, `backend/app/schemas.py`(CardState/EndingResponse.card), `backend/app/api/common.py`(is_card_available/serialize_card), `docs/api-contract.md`, 프론트 카드 컴포넌트
  - 수정 범위: API 계약 변경(양쪽 팀 확인 필요), 테이블 스키마 자체는 유지 가능(의미만 재정의)해도 되고 완전 교체 시 마이그레이션 필요
  - 예상 영향: 계약 변경이라 CLAUDE.md 13장 규칙상 사용자 확인 필수
- 항목: 캐릭터 나이/성별 변경
  - 관련 파일: `backend/app/images/prompts.py`(_CHARACTER_TEMPLATE의 "27-year-old Korean woman" 등 하드코딩 문구)
  - 수정 범위: 문자열 1곳(단, PERSONA_YAML과 별개 파일이라 두 곳을 잊지 않고 같이 고쳐야 함)
  - 예상 영향: 안 고치면 이미지와 대사 설정이 어긋남(예: 대사는 새 캐릭터인데 이미지는 여전히 27세 여성으로 나옴)
- 항목: 여러 캐릭터 등장(현재 1인 고정 구조를 다중 캐릭터로 확장)
  - 관련 파일: 프롬프트 조립 전체(`llm/prompts.py`), 이미지 참조 구조(`images/service.py`, 현재 portrait 1장만 참조), NEGATIVE_BLOCK("No other people in frame"), DB 스키마(현재 세션당 캐릭터 슬롯 없음)
  - 수정 범위: 사실상 재설계 수준(가장 비용이 큰 변경)
  - 예상 영향: 이 프로젝트의 핵심 설계 전제(참조 이미지 1장으로 일관성 확보)와 정면충돌

## 현재 스토리의 교체 가능한 사건
- Scene 1: 코드가 강제하는 사건 없음(턴 전환만 강제). "마지막 정리 시작" 서사는 완전히 다른 도입부로 교체 가능.
- Scene 2: 코드가 강제하는 사건 없음. "책+책갈피 발견"은 다른 소품/사건으로 완전 교체 가능(소유권 이진 상태 구조는 재사용 시 비용 최소).
- Scene 3: **카드 UI 게이트**(scene_id>=3)만 코드 강제. 카드에 "무엇을 남기는가"의 서사는 자유.
- Scene 4: **턴12 강제 확정 사건 1개**(현재 door_locked)만 코드 강제. 그 사건의 이름/서사적 의미는 자유, "턴12에 반드시 확정된다"는 역할만 유지.

## ChatGPT에게 전달할 핵심 구현 사양

아래는 스토리를 새로 설계할 때 그대로 참고할 수 있는 독립적인 사양 요약이다.

- **목표 플레이타임:** 10~15분(강제 타이머 없음, 대화 응답 길이 제약과 이미지 생성 지연이 실질적으로 이 시간을 결정)
- **총 턴:** 12(플레이어 입력 1회 + 캐릭터 응답 1회 = 1턴). 서버 상수라 바꿀 수 있으나 API 계약엔 숫자가 고정 노출되지 않음.
- **장면 수:** 4개, 장면당 3턴 균등 분배(변경 가능, 이미 장면4만 4턴으로 늘리는 대안이 문서화돼 있음).
- **캐릭터 수:** 1명(플레이어 상대역) + 플레이어. 다중 캐릭터는 사실상 재설계급 변경.
- **이미지 구조:** 회차당 정확히 6장(초상화1 + 장면당1×4 + 엔딩1). 초상화 1장만 모든 후속 이미지의 참조로 재사용. 장면 이미지 4장은 대화 내용과 무관하게 완전히 고정된 구도/포즈(장면 번호에만 의존). 엔딩 이미지 1장만 5개 상태값(장소=마지막 장면, 자세=마지막사건 확정여부, 표정=관계상태 3분기, 소품=카드/책 소유, 거리감=동석여부)의 조합으로 동적 결정.
- **반드시 유지해야 하는 UI:** 카드 작성 인터랙션(전용 API/테이블), 엔딩 화면의 "결말에 남은 대화"(evidence 인용, 최대 3개), 장면별 좌측 이미지 컬럼.
- **반드시 유지해야 하는 state:** `scene_id`(1~4), `completed_turns`(0~12), 카드 상태(decided/written/text/author), 턴12에 강제 확정되는 사건 플래그 1개. 그 외 상태값(소유권류, 약속류)은 이름과 개수를 자유롭게 재설계 가능하되, "LLM 제안 → 서버가 허용목록으로 검증 후에만 확정"이라는 처리 방식 자체는 유지 필요(새 이벤트 타입마다 서버 코드에 대응 함수 추가 필요, 프롬프트만으로는 상태가 안 바뀜).
- **교체 가능한 사건:** 장면1~3의 모든 사건(강제되는 코드 로직 없음), 장면4의 사건 중 "턴12 강제 확정 사건"을 제외한 나머지(10·11턴의 자유 대화).
- **교체 불가능하거나 비용이 큰 사건:** 카드 인터랙션의 존재 자체(API/UI 구조), 턴12에 무언가 하나는 강제로 확정된다는 것, 참조 이미지 1장/캐릭터 1인 전제.
- **엔딩 생성 방식:** 텍스트(제목 8~20자, 본문 350~550자, 미해결 0~2개)는 LLM이 생성하되 근거 인용문은 DB 원문을 그대로 사용(LLM이 인용문을 재작성하지 않음, 최대 3개, 특정 이벤트 타입에서만 근거로 채택됨). 엔딩 이미지는 자유생성이 아니라 5개 슬롯에 미리 정의된 영문 조각 중 하나씩 서버가 상태값으로 골라 채우는 방식(LLM이 이미지 프롬프트를 직접 쓰지 않음).
- **기타 제약:** 대화 응답은 120~200자(장면전환만 250자) 2~4문장, 매번 질문으로 끝내지 않음, 캐릭터 외형(머리/눈/안경/체형)은 대사에 등장 금지(이미지와 불일치 방지, 의상·소품은 언급 가능), 사용자 입력이 이미지 프롬프트에 직접 반영되는 경로 없음(항상 서버 확정 상태값을 경유), 1턴=1회 LLM 호출(해석과 생성을 분리하지 않음), 실제 이미지 생성 지연은 문서 가정(5초)과 달리 장당 20~30초로 확인됨(플레이타임 설계 시 참고).
