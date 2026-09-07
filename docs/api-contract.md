# API 계약 — 마지막 책갈피

이 문서가 백엔드(Claude)와 프론트(Codex)의 유일한 접점이다. **여기를 바꿔야 하면 어느 쪽
작업이든 반드시 사용자에게 먼저 확인받는다.** 계약이 어긋나면 두 작업 다 고쳐야 한다.

`CLAUDE.md`·`AGENTS.md`는 각자 이 문서를 참조한다. 계약 내용을 자기 파일에 다시 옮겨 적지
않는다 — 한 곳만 고치면 되게 유지하기 위해서다.

## 엔드포인트

| 메서드 | 경로 | 용도 |
|---|---|---|
| POST | `/api/auth/verify` | 초대 코드 검증, 토큰 발급 |
| GET | `/api/sessions` | 해당 코드의 회차 목록 |
| POST | `/api/sessions` | 외형 프리셋으로 회차 생성 + 초상화 |
| DELETE | `/api/sessions/{id}` | 회차 삭제 (진행 중·완료 상관없이) |
| POST | `/api/sessions/{id}/portrait/retry` | 초상화 재생성 (최대 2회) |
| POST | `/api/sessions/{id}/start` | 초상화 확정 |
| GET | `/api/sessions/{id}` | 회차 상태·메시지·이미지 복원 |
| POST | `/api/sessions/{id}/turns` | 턴 제출 |
| POST | `/api/sessions/{id}/card` | 카드 확정 또는 빈 채로 두기 |
| POST | `/api/sessions/{id}/end` | 메뉴 조기 종료 |
| GET | `/api/sessions/{id}/ending` | 엔딩 본문·근거·이미지 상태 |
| POST | `/api/sessions/{id}/ending/image/retry` | 엔딩 이미지 재생성 |
| GET | `/api/images/{image_id}` | 저장된 이미지 파일 |

**`/admin`, `/api/admin/usage`는 이 계약에 없다.** 게임 화면과 무관한 별도 관리자 도구(비용
모니터링)이며 프론트 구현 대상이 아니다.

## 멱등키(`request_id`)가 필요한 요청

응답 유실 후 재시도해도 중복 생성되지 않도록, 아래 요청은 본문에 `request_id`(string)가
**필수**다. 같은 `request_id`로 재전송하면 처음 응답을 그대로 돌려받는다.

- `POST /api/sessions` — `{ "request_id": "...", "presets": {...} }`
- `POST /api/sessions/{id}/portrait/retry` — `{ "request_id": "..." }`
- `POST /api/sessions/{id}/turns` — `{ "request_id": "...", "text": "..." }`
- `POST /api/sessions/{id}/card` — `{ "request_id": "...", "action": "write"|"leave_blank", "text": "..." }`
- `POST /api/sessions/{id}/end` — `{ "request_id": "..." }`

새로 생성을 요청할 때(예: "다시 그리기"를 사용자가 명시적으로 또 눌렀을 때)는 새
`request_id`를 발급한다.

## 주요 응답 형태

### 회차 목록 (`GET /api/sessions`)

```json
{
  "sessions": [
    {
      "id": "uuid",
      "index": 3,
      "status": "completed",
      "completed_turns": 12,
      "ending_title": "문을 닫은 뒤에도 남는 말",
      "portrait_url": "/api/images/...",
      "created_at": "2026-09-05T20:11:00+09:00"
    }
  ]
}
```

`status`는 `in_progress` / `completed` / `ended_early` 세 가지다.

### 회차 삭제 (`DELETE /api/sessions/{id}`)

성공 시:

```json
{ "status": "deleted", "id": "uuid" }
```

존재하지 않거나 다른 코드 소유 회차는 404.

### 회차 복원 (`GET /api/sessions/{id}`)

```json
{
  "id": "uuid",
  "status": "in_progress",
  "completed_turns": 5,
  "story_time": "20:41",
  "scene": { "id": 2, "name": "남겨둔 책", "entered": false, "image_url": "..." },
  "scenes": [
    { "id": 1, "name": "마지막 손님", "image_url": "..." },
    { "id": 2, "name": "남겨둔 책", "image_url": "..." },
    { "id": 3, "name": "쓰지 못한 한 문장", "image_url": null },
    { "id": 4, "name": "문을 닫기 전에", "image_url": null }
  ],
  "messages": [ /* 아래 턴 응답의 messages와 같은 형태, turn=0(오프닝 대사) 포함 */ ],
  "card_available": false,
  "is_final_turn": false,
  "portrait": { "status": "done", "url": "...", "retry_count": 0, "retry_limit": 2 },
  "portrait_confirmed": true,
  "presets": { "hair_length": "bob", "hair_color": "dark_brown", "bangs": "full",
               "eyes": "sharp", "glasses": "none", "impression": "calm", "build": "average" }
}
```

- `scenes`: 지금까지 지나온 장면 포함 4개 전부. 완료 회차를 다른 브라우저에서 열어도 장면
  4장을 그대로 복원할 수 있게 하기 위함이다. 아직 생성 안 된 장면은 `image_url: null`.
- `portrait_confirmed`, `presets`: 초상화만 만들고 "이 모습으로 시작하기"를 누르기 전에
  이탈한 회차인지 구분해, 재진입 시 초상화 확인 화면/대화 화면 중 올바른 쪽으로 보내기
  위함이다.
- `messages`에는 `turn=0`인 오프닝 메시지(story.md 6.1의 첫 화면 설명·시작 대사)가 포함된다.
  프론트가 따로 하드코딩할 필요 없다.

### 턴 응답 (`POST /api/sessions/{id}/turns`, `POST /api/sessions/{id}/card`)

```json
{
  "messages": [
    { "id": "m_014", "turn": 5, "kind": "player", "text": "..." },
    { "id": "m_015", "turn": 5, "kind": "reply", "text": "..." },
    { "id": "m_016", "turn": 5, "kind": "narration", "text": "..." },
    { "id": "m_017", "turn": 5, "kind": "record", "record_type": "promise", "text": "..." }
  ],
  "completed_turns": 5,
  "story_time": "20:41",
  "scene": { "id": 2, "name": "남겨둔 책", "entered": false, "image_url": "..." },
  "card_available": false,
  "is_final_turn": false
}
```

`kind`는 `player` / `reply` / `narration` / `record` 네 가지다. `record_type`은 `promise` /
`fact` / `memory`. **내부 수치(trust/closeness/tension)는 어떤 응답에도 넣지 않는다.**

### 장면 이미지 준비 시점

장면 1~4 이미지는 **회차 생성(초상화 성공) 직후부터 백그라운드로 미리 만들어진다** —
`POST /sessions/{id}/start`를 기다리지 않는다. `/start`는 즉시 반환하며, 이미 준비됐으면
`scene.image_url`이 채워져 오고 아직이면 `null`이다(장면 2~4와 같은 스켈레톤+폴링 패턴을
장면 1에도 그대로 적용하면 됨). `GET /api/sessions/{id}`를 폴링해 `scenes` 배열이 채워지는지
확인한다.

### 엔딩 (`GET /api/sessions/{id}/ending`)

```json
{
  "title": "...",
  "body": "...",
  "card": { "written": true, "text": "...", "author": "player" },
  "evidence": [
    {
      "message_id": "m_014",
      "turn": 5,
      "story_time": "20:41",
      "scene_name": "남겨둔 책",
      "quote": "플레이어가 실제로 입력한 원문",
      "effect": "이 말이 마지막 부탁의 바탕이 되었다."
    }
  ],
  "unresolved": ["새 서점의 장소는 정해지지 않았다."],
  "image": { "status": "generating", "url": null }
}
```

`quote`는 **DB의 원문을 그대로** 넣는다. LLM이 다시 쓴 문장을 넣지 않는다. **카드 문장은
`evidence` 배열이 아니라 `card` 필드에 원문 그대로 들어간다** — 카드 원문을 근거 대화용
플레이어 메시지 ID에 억지로 연결할 필요 없다.

### 인증 실패 응답

`POST /api/auth/verify`가 실패하면 상황에 따라 다른 상태 코드와 `detail` 메시지를 준다.
프론트는 상태 코드별로 다르게 처리하지 말고, **`detail` 텍스트를 그대로 보여주면 된다** —
서버가 이미 상황에 맞는 한국어 문구를 담아서 보낸다.

- `401`: 코드가 틀림 (`"초대 코드가 올바르지 않습니다."`)
- `429`: 같은 IP에서 짧은 시간에 너무 자주 시도함
- `403`: 임시 차단됐거나(무차별 대입 시도로 판단), 이 코드가 특정 위치에서만 쓰도록
  제한되어 있음
