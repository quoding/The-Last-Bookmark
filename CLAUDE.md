# CLAUDE.md — 마지막 책갈피

이 파일은 Claude Code가 이 저장소에서 작업할 때 따르는 지침이다.

## 0. 먼저 읽을 것

작업 시작 전 `docs/` 아래 문서를 반드시 읽는다.

- `docs/story.md` — 세계관, 캐릭터 한서윤, 장면 의도, 엔딩 서사 규칙. **무엇을 만드는가**
- `docs/ui-spec.md` — 화면 구성, 턴별 시각 테이블, 카드 인터랙션. **어떻게 보이는가**
- `docs/api-contract.md` — 백엔드·프론트(Codex)의 유일한 접점인 API 계약. **원본은 여기다.**
  이 파일(6장)에는 더 이상 계약 내용을 옮겨 적지 않는다
- `docs/ops-notes.md` — 백엔드·프론트 공통 운영 규칙(시크릿 관리, 배포 폴더 구조 등).
  Codex의 `AGENTS.md`도 같은 문서를 본다

이 파일은 **어떻게 구현하는가**(백엔드 한정)를 다룬다. 게임 내용을 여기서 다시 정의하지 않는다.

문서가 충돌하면 서사와 캐릭터는 story.md, 화면 동작은 ui-spec.md, API 계약은
api-contract.md, 공통 운영 규칙은 ops-notes.md, 그 외 백엔드 구현 방식은 이 파일을 따른다.

## 1. 프로젝트 개요

폐점을 앞둔 독립서점에서 30분 동안 캐릭터와 대화하고, **플레이어가 실제로 한 말이 근거로 남는 결말과 일러스트**를 받는 한국어 인터랙티브 로맨스 웹 게임.

- 4장면 12턴 고정. 이야기 속 시간 20:30~21:00
- 실제 플레이 10~15분
- 회차 시작 시 플레이어가 캐릭터 외형을 프리셋으로 선택
- 회차마다 이미지 6장 생성 (초상화 1 + 장면 4 + 엔딩 1)
- 채용 포트폴리오용 데모. 초대 코드를 가진 소수만 접속

**이 프로젝트가 증명하려는 것:** 자유 대화를 구조화된 사건으로 확정하고, 그 사건을 근거로 매번 다른 결말을 생성하며, 사용자가 그 인과를 눈으로 확인할 수 있다는 것.

## 2. 작업 분담

**프론트엔드 UI는 별도 도구(Codex)로 작업한다.** Claude Code는 다음을 담당한다.

- 백엔드 전체 (FastAPI, DB, 마이그레이션)
- LLM 연동과 프롬프트 조립
- 이미지 생성 연동
- 장면 엔진과 상태 관리
- 배포 설정

프론트 코드를 임의로 수정하지 않는다. **API 계약(6장)이 두 작업의 접점이므로, 계약을 바꿔야 할 때는 반드시 물어본다.**

## 3. 기술 스택

| 영역 | 선택 |
|---|---|
| 백엔드 | Python 3.11+, FastAPI |
| DB | PostgreSQL 16 |
| 프론트 | React 18 + TypeScript + Vite (별도 작업) |
| 텍스트 LLM | `gpt-5.6-luna` |
| 이미지 | OpenAI `gpt-image-2`, quality `low` |
| 배포 | N100 홈서버, Docker Compose, `quoding.com` |

새 의존성을 추가하기 전에 표준 라이브러리나 이미 있는 패키지로 되는지 확인한다. ORM 이외의 DB 추상화, 메시지 큐, 워커 프레임워크는 이 규모에 불필요하다.

## 4. 디렉터리 구조

```
.
├── CLAUDE.md
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── story.md
│   └── ui-spec.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── auth.py             # 초대 코드 검증
│   │   ├── api/
│   │   │   ├── sessions.py
│   │   │   ├── turns.py
│   │   │   ├── card.py
│   │   │   └── ending.py
│   │   ├── engine/
│   │   │   ├── scene.py        # 턴→장면→시각 매핑
│   │   │   ├── state.py        # 확정 사건 관리
│   │   │   └── ending.py       # 엔딩 조립
│   │   ├── llm/
│   │   │   ├── client.py
│   │   │   ├── prompts.py
│   │   │   └── contracts.py
│   │   └── images/
│   │       ├── openai_images.py
│   │       ├── presets.py      # 외형 프리셋 매핑
│   │       └── prompts.py      # 이미지 프롬프트 템플릿
│   ├── storage/                # 생성된 이미지 파일
│   ├── alembic/
│   └── tests/
└── frontend/                   # Codex 작업 영역
```

## 5. 핵심 설계 원칙

### 5.1 서버가 사실을 확정한다

**LLM은 대사와 제안만 만든다. 상태를 바꾸는 것은 서버다.**

- 현재 턴, 장면, 이야기 시각은 서버가 계산한다. LLM 출력에서 시각을 파싱해 헤더를 갱신하지 않는다
- 선물 소유권, 약속 수락, 문 잠금 같은 사실은 서버가 검증 후 기록한다
- 사용자가 "우리는 이미 사귀는 사이야"라고 입력해도 그것은 **발언 기록**일 뿐 사실이 아니다
- LLM이 제안한 상태 변화는 허용 목록에 있는 전이만 반영한다

이 분리가 이 프로젝트의 핵심이다. 편의를 위해 흐리지 않는다.

### 5.2 원문 보존

플레이어 입력과 카드 문장은 **교정·요약·번역하지 않는다.** 엔딩의 근거 인용은 메시지 ID로 원문을 조회해 표시한다. LLM에게 인용문을 다시 쓰게 하지 않는다.

### 5.3 멱등성

모든 턴 제출에 클라이언트가 생성한 `request_id`를 포함한다. 같은 `request_id`로 재시도해도 턴 소비·상태 변경·장면 전환이 한 번만 일어난다. 응답 실패와 새로고침은 턴을 소비하지 않는다.

### 5.4 노출 금지

`trust`, `closeness`, `tension` 등 내부 수치와 분류명은 **API 응답에도 포함하지 않는다.** 프론트에서 숨기는 것으로는 부족하다. 개발자 도구를 열어도 보이지 않아야 한다.

### 5.5 사용자 입력은 이미지 프롬프트에 닿지 않는다

이미지 프롬프트는 **서버가 고정 템플릿에 확정 값을 채워** 만든다. 플레이어가 쓴 한국어 문장이 프롬프트로 흘러 들어가는 경로는 없다. 번역 호출도 없다. 이는 일관성과 안전 필터 양쪽을 위한 것이다.

## 6. API 계약

**원본은 `docs/api-contract.md`다.** 엔드포인트 목록, 멱등키가 필요한 요청, 응답 JSON
형태가 전부 거기 있다. 이 파일에는 더 이상 계약 내용을 옮겨 적지 않는다 — 백엔드가 계약을
바꿀 때는 `docs/api-contract.md`를 고치고, **반드시 사용자에게 먼저 확인받는다.**

## 7. 외형 프리셋과 이미지 프롬프트

### 7.1 원칙

한글 라벨과 영문 프롬프트 조각을 **쌍으로 정의된 상수**로 관리한다. 번역 호출을 하지 않는다. 같은 선택은 항상 같은 영문을 만든다.

영문 조각은 이미지 모델이 잘 알아듣는 표현으로 튜닝한 결과이며, 직역이 아니다. 수정할 때는 실제로 생성해 보고 바꾼다.

### 7.2 프리셋 매핑

```python
PRESETS = {
    "hair_length": [
        ("bob",       "단발",              "a chin-length bob"),
        ("shoulder",  "어깨 길이",          "shoulder-length hair"),
        ("long",      "등까지 오는 긴 머리",  "long hair falling past the shoulders"),
        ("short",     "짧은 층 있는 머리",    "short layered hair"),
    ],
    "hair_color": [
        ("dark_brown", "짙은 갈색",    "dark brown"),
        ("black",      "검정",         "black"),
        ("ash_brown",  "애쉬 브라운",   "ash brown"),
        ("auburn",     "어두운 적갈색", "dark auburn"),
    ],
    "bangs": [
        ("full",    "있음",             "straight-across bangs"),
        ("swept",   "없음(옆으로 넘긴)",  "no bangs, hair swept to the side"),
        ("center",  "가운데 가르마",      "a center part, no bangs"),
    ],
    "eyes": [
        ("sharp",    "또렷한",   "clear, well-defined eyes"),
        ("droopy",   "처진",     "gently downturned eyes"),
        ("languid",  "나른한",   "relaxed, half-lidded eyes"),
        ("soft",     "부드러운", "soft, rounded eyes"),
    ],
    "glasses": [
        ("round",  "얇은 둥근 테", "thin round metal-framed glasses"),
        ("square", "사각 뿔테",    "square tortoiseshell glasses"),
        ("none",   "없음",        "no glasses"),
    ],
    "impression": [
        ("calm",   "차분한", "a calm, composed expression"),
        ("warm",   "다정한", "a warm, gentle expression"),
        ("cool",   "서늘한", "a cool, reserved expression"),
    ],
    "build": [
        ("petite",  "작고 아담한", "petite and slight"),
        ("average", "보통",       "average height and build"),
        ("tall",    "크고 마른",   "tall and slender"),
    ],
}
```

조합 수는 4×4×3×4×3×3×3 = 5,184.

### 7.3 프롬프트 3단 구조

```
[STYLE] + [CHARACTER] + [SCENE] + [NEGATIVE]
```

**STYLE — 모든 이미지 공통**

```
Soft 2D anime-style romance illustration, restrained and painterly.
Muted, low-saturation palette. Warm indoor lighting with cool blue night
tones outside. Gentle linework, no harsh contrast. Vertical composition,
full-body framing with headroom.
```

**CHARACTER — 초상화 생성에만 전문 사용**

```
A 27-year-old Korean woman, a quiet independent bookstore owner.
{hair_length}, {hair_color} hair, {bangs}. {eyes}. {glasses}.
{impression}. {build}.
She wears a cream-colored knit sweater and a dark green apron,
with a small silver pen in the apron's left pocket.
```

장면·엔딩 이미지에서는 참조 이미지가 외형을 담당하므로 다음 짧은 요약만 쓴다.

```
The same woman as in the reference image, wearing the same cream knit
sweater and dark green apron.
```

**NEGATIVE — 모든 이미지 공통**

```
No readable text anywhere. No signage, no book titles, no handwriting.
No other people in frame. No modern logos or brand marks.
```

### 7.4 장면 프롬프트 — 고정 템플릿

외형이 바뀌어도 장면 문구는 고정이다.

```python
SCENE_PROMPTS = {
    1: """Standing in a narrow aisle between wooden bookshelves,
         cardboard packing boxes on the floor around her.
         She has just set down a box and is turning to look toward
         the viewer, a faint tired smile. Warm ceiling lights,
         shelves half-empty.""",

    2: """Standing behind the shop counter, a single short story
         collection in her hands with a frayed navy-blue cloth
         bookmark tucked into it. A small desk lamp on the counter
         lights the book from the side. She is offering it forward.""",

    3: """Seated at a small table by the front window, a blank cream
         card and a silver pen in front of her. Rain streaks the glass;
         cool blue light from outside mixes with the warm interior lamp.
         She rests her chin lightly on one hand, thinking.""",

    4: """Standing outside the shop entrance under the awning at night,
         the darkened storefront behind her, a ring of keys in her hand.
         Streetlight and wet pavement reflections light her from the
         front. Light rain. She has just turned back from the locked door.""",
}
```

장면마다 **공간이 다르다** (통로 / 카운터 / 창가 / 문 밖). 같은 배경을 반복하지 않아 회차마다 이미지가 미묘하게 달라도 이질감이 덜하다.

장면 4는 실내가 어두우므로 **바깥 광원**으로 화면을 밝힌다. 세로 이미지가 화면 절반을 차지하는데 너무 어두우면 답답하다.

### 7.5 엔딩 프롬프트 — 슬롯 채우기

확정된 사건으로 슬롯을 채운다. 각 슬롯의 값은 **미리 정의된 영문 조각 중 하나**이며, 자유 생성하지 않는다.

```python
ENDING_TEMPLATE = """
{location}. {posture}. {expression}.
{props}. {distance}.
"""
```

| 슬롯 | 값의 예 | 결정 근거 |
|---|---|---|
| `location` | 처마 아래 / 잠긴 문 앞 / 카운터 뒤 | `player_present`, `door_locked` |
| `posture` | 돌아서서 바라보는 / 어깨의 힘을 푼 / 정리하는 | 마지막 행동 기록 |
| `expression` | 조심스러운 미소 / 시선을 내린 / 편안한 | 관계 상태 |
| `props` | 열쇠만 / 책을 든 / 카드를 쥔 | `book_owner`, `card_owner` |
| `distance` | 가까이 마주 선 / 한 걸음 떨어진 / 혼자 | `player_present`, 접촉 기록 |

**기록과 어긋나는 조합을 만들지 않는다.** 책갈피를 플레이어가 가져갔으면 서윤 손에 그리지 않는다. 카드가 빈 채면 글씨 있는 카드로 그리지 않는다.

## 8. 텍스트 LLM — gpt-5.6-luna

### 8.1 턴당 호출 구조

**1턴 = 1회 호출.** 하나의 응답에서 대사와 상태 변화 제안을 함께 받는다.

```
입력: 시스템 프롬프트(페르소나 + 현재 장면 + 확정 상태 + 최근 대화)
      + 플레이어 입력
출력: { "reply": "...", "narration": "...", "proposed_events": [...] }
```

`proposed_events`는 **제안**이다. 서버가 5.1의 규칙으로 검증한 뒤에만 확정한다.

해석과 대사 생성을 2회 호출로 분리하면 지연이 두 배가 되므로 채택하지 않는다. 구조화 출력 신뢰도가 실측으로 부족하다고 확인되면 그때 분리를 검토한다.

### 8.2 구조화 출력

Structured Outputs를 우선 시도한다. 미지원이거나 준수율이 낮으면 다음 순서로 처리한다.

1. 엄격한 JSON 스키마 검증
2. 실패 시 최대 2회 재시도. 재시도는 턴을 소비하지 않는다
3. 그래도 실패하면 `reply`만 살리고 `proposed_events`는 빈 배열로 처리한 뒤 로깅한다

**대사가 나오는 것이 사건 추출보다 우선이다.** 사건을 못 뽑았다고 플레이어에게 오류를 보여주지 않는다.

### 8.3 응답 제약

- 대사·묘사 합쳐 **120~200자** 기본, 장면 전환만 250자까지
- 2~4개의 짧은 문장
- 응답 끝을 매번 질문으로 만들지 않는다
- **캐릭터 외형을 언급하지 않는다** (story.md 5.5). 의상과 소품은 가능

길이 제약은 프롬프트로 지시하고, 초과 시 자르지 말고 로깅만 한다.

### 8.4 프롬프트 조립

`llm/prompts.py`에서 조합한다.

1. 페르소나 (story.md 12장 YAML)
2. 현재 장면의 목적·공간·고정 사건
3. 확정된 상태 요약 (소품 소유, 수락된 약속, 공개된 정보)
4. 최근 대화 6~8턴
5. 금지 사항 (story.md 4.3, 5.3, 5.5, 7.3)

story.md의 내용과 1:1로 대응하는 상수로 관리한다. 스토리가 바뀌면 프롬프트도 따라 바뀌어야 한다.

## 9. 이미지 — OpenAI GPT Image 2 (low)

### 9.1 호출

| 용도 | 엔드포인트 | 참조 |
|---|---|---|
| 초상화 | `POST /v1/images/generations` | 없음 |
| 장면 4장 | `POST /v1/images/edits` | 초상화 1장 |
| 엔딩 | `POST /v1/images/edits` | 초상화 1장 |

편집 엔드포인트는 `multipart/form-data`이며 참조 이미지를 `image[]` 반복 필드로 넘긴다.

| 파라미터 | 값 |
|---|---|
| `model` | `gpt-image-2` |
| `quality` | `low` |
| `size` | `1024x1536` (세로 고정) |
| `n` | 1 |
| `output_format` | `webp` |

생성 시간은 장당 5초 내외로 확인됐다. low 세로 이미지는 약 $0.005이며 참조 포함 편집은 입력 토큰이 추가된다. 회차당 6장으로 $0.05 안팎을 예상한다.

### 9.2 캐릭터 일관성

**초상화 1장만 참조로 사용한다.** 장면 4장과 엔딩 모두 같은 초상화를 참조한다. 참조를 늘리지 않는다.

초상화가 그 회차의 기준이므로, 초상화 생성에 실패하면 회차를 시작하지 않는다.

참조가 동일인물을 보장한다고 가정하지 않는다. 결과를 검수하고, 재현이 반복 실패하면 인물을 빼고 사물·공간 중심으로 전환하는 선택지를 남긴다. 이는 폴백이 아니라 정당한 연출이다.

### 9.3 생성 시점

| 이미지 | 시점 |
|---|---|
| 초상화 | 외형 확정 시 동기 생성. 완료를 기다린다 |
| 장면 1 | 회차 시작 직후. 대화 화면 진입 전 완료 대기 |
| 장면 2~4 | 회차 시작 직후 백그라운드. 대화 중 준비됨 |
| 엔딩 | 12턴 완료 또는 조기 종료 시 백그라운드 |

장면 2는 3턴 후(2~3분 뒤)에 필요하므로 백그라운드 생성이 충분히 끝난다. 미완성이면 좌측에 스켈레톤을 표시하고 대화는 계속 진행한다.

### 9.4 저장

OpenAI가 주는 URL은 만료되므로 **생성 즉시 파일로 내려받아 `backend/storage/`에 저장**하고 경로를 DB에 기록한다. 프론트는 `/api/images/{image_id}`로 접근한다.

회차당 6장이므로 용량은 무시할 수준이다. 회차를 삭제하지 않는 한 이미지도 남긴다.

### 9.5 안전 필터

OpenAI의 콘텐츠 정책이 적용된다. 프롬프트는 **행동과 공간 중심의 절제된 서술**로 작성한다. 5.5에 따라 사용자 입력이 프롬프트에 닿지 않으므로 거부는 드물어야 한다.

거부 응답을 일반 오류로 처리하지 말고 별도 상태로 기록한다. 사용자에게는 이미지 없이 본문만 보여준다.

### 9.6 비동기 처리

FastAPI의 `BackgroundTasks` + DB 상태 테이블로 처리한다. 큐 인프라는 이 규모에 과하다.

1. 작업 행을 `pending`으로 만들고 즉시 반환
2. 백그라운드에서 생성·저장 후 `done` 또는 `failed`
3. 프론트가 폴링
4. 재진입 시 상태 복원. 같은 이미지를 두 번 생성하지 않는다

## 10. 인증과 회차

### 10.1 초대 코드

유효 코드는 두 개다: `muya98`(개발자용 식별자), `tainai`(심사용 식별자). **이 두 문자열은 코드 식별자(code_id)이지 실제로 입력하는 비밀 문자열이 아니다.** 실제 초대 코드 평문은 이 저장소 어디에도 적지 않는다 — 환경변수(`INVITE_CODE_HASHES`, gitignore 대상)에 해시로만 저장하고 서버에서 비교한다. 이 문서는 public 저장소에 커밋되므로 평문을 적으면 그대로 유출된다(과거에 이 문서에 평문을 직접 적어뒀다가 유출되어 코드를 교체한 적이 있다 — 되풀이하지 않는다).

검증 성공 시 코드 식별자를 담은 토큰을 발급한다. 회차는 코드별로 분리 저장된다.

### 10.2 회차 저장

- 코드별로 여러 회차를 보관한다. 새 회차가 이전 회차를 덮어쓰지 않는다
- 완료된 회차는 읽기 전용으로 다시 볼 수 있다. 대화 로그, 엔딩, 이미지 6장 모두 보존
- 미완료 회차는 이어하기 가능
- 과거 회차의 엔딩을 다시 생성하지 않는다

`IMAGE_BUDGET_SESSIONS`를 회차 수 기준으로 둔다. 초과하면 새 회차 생성을 막고 안내한다.

## 11. 개발 규칙

### 11.1 작업 순서

1. DB 스키마와 장면 엔진 (턴→시각 매핑을 테스트로 고정)
2. 초대 코드 인증과 회차 생성
3. 외형 프리셋과 초상화 생성
4. LLM 호출과 구조화 출력 검증
5. 턴 처리와 상태 확정
6. 카드 인터랙션
7. 엔딩 생성과 근거 인용
8. 장면·엔딩 이미지 연동
9. 회차 목록과 읽기 전용 조회
10. 배포

**7번까지가 이 프로젝트의 본체다.** 이미지가 늦어져도 7번이 완성되면 데모는 성립한다.

### 11.2 테스트

`docs/story.md` 13장의 7개 경로(A~G)를 통합 테스트로 만든다. 특히 다음을 검증한다.

- 경로 E: 사용자가 세계 상태를 지정해도 서버 사실이 바뀌지 않음
- 경로 D, F: 발생하지 않은 사건이 엔딩에 등장하지 않음
- 경로 G: 대사에 캐릭터 외형이 등장하지 않음
- 턴 3·6·9 완료 시 장면 전환이 한 번만 일어남
- 같은 `request_id` 재전송 시 턴이 두 번 소비되지 않음
- 프리셋 조합이 항상 같은 영문 프롬프트를 만듦

LLM과 이미지 호출은 목으로 대체한다. 프롬프트 조립과 상태 전이는 실제 호출 없이 테스트 가능해야 한다.

### 11.3 커밋

- 한글 커밋 메시지. 무엇을 왜 바꿨는지 한 줄
- 기능 단위로 나눈다. "여러 파일 수정" 같은 뭉뚱그린 커밋 금지
- 이 프로젝트는 포트폴리오다. **커밋 히스토리 자체가 산출물이다**

### 11.4 환경 변수

```
LLM_API_KEY=
LLM_MODEL=gpt-5.6-luna
IMAGE_API_KEY=
IMAGE_MODEL=gpt-image-2
IMAGE_QUALITY=low
IMAGE_SIZE=1024x1536
DATABASE_URL=
INVITE_CODE_HASHES=      # 콤마 구분
IMAGE_BUDGET_SESSIONS=   # 허용 회차 수 상한
STORAGE_PATH=./storage
```

## 12. 하지 말 것

- 게임 규칙이나 캐릭터 설정을 이 파일이나 코드에서 새로 정의하기. `docs/`가 기준이다
- LLM 출력을 검증 없이 상태에 반영하기
- 내부 수치를 API 응답에 포함하기
- 플레이어 입력이나 카드 문장을 교정·요약하기
- 사용자 입력을 이미지 프롬프트에 넣기
- 프리셋 라벨을 LLM으로 번역하기
- 이미지에 한국어 렌더링을 요구하기
- 대사나 서술에서 캐릭터 외형을 묘사하기
- 워커·큐·낙관적 락 같은 인프라를 미리 만들기
- 프론트엔드 코드를 임의로 수정하기
- 발생하지 않은 사건을 엔딩이나 이미지에 넣기

## 13. 판단이 필요할 때

**물어볼 것**

- API 계약(6장)을 바꿔야 할 때
- `docs/`의 두 문서가 충돌하고 어느 쪽을 따를지 애매할 때
- 12턴 구성이나 시각 테이블을 바꿔야 할 것 같을 때
- 새 외부 의존성이 필요할 때
- 참조 이미지로도 캐릭터 외형이 유지되지 않을 때
- 프리셋 축이나 선택지를 늘리거나 줄여야 할 때
- 구조화 출력 실패율이 높아 호출 구조를 바꿔야 할 때

**물어보지 말고 진행할 것**

- 파일 분할, 함수 이름, 타입 정의
- 테스트 추가
- 에러 처리 보강
- 마이그레이션 작성
- 로깅 추가
