# 마지막 책갈피 프론트엔드

Vite + React 18 + TypeScript + CSS Modules. 런타임 의존성은 React와 React DOM뿐입니다.

## 실행

```sh
cd frontend
npm install
npm run dev
```

기본은 목 모드입니다. **4자 이상 임의의 초대 코드**로 들어갈 수 있습니다. 실제 초대 코드의 정답은 번들에 넣지 않았습니다. 같은 코드는 같은 브라우저에서 같은 목 회차를 복원합니다. 코드마다 회차가 분리되고, 1분 동안 인증 시도는 5회로 제한합니다. 실제 코드 검증과 접근 제한은 API 서버가 담당합니다.

처음에는 완료 회차 2개와 7턴까지 진행한 회차 1개가 있습니다. 완료 회차를 열면 엔딩 근거 카드 3개를 바로 검수할 수 있습니다. 이미지들은 외부 요청 없는 로컬 SVG 플레이스홀더입니다. 실제 생성 결과를 흉내 낸 최종 자산이 아닙니다.

## 실제 API로 전환

`.env.local`에 API 원점을 지정하고 Vite를 다시 실행합니다.

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

`mock://local`이면 지연·실패·저장을 처리하는 목 전송 계층을 지연 로드합니다. HTTP(S) 원점이면 동일한 클라이언트가 fetch를 사용합니다. `/api`는 원점에 포함하지 않습니다. 요청에는 Bearer 토큰을 붙이고, 상대 이미지 URL도 지정한 원점으로 해석합니다.

주요 응답 타입은 `src/types/api.ts`, 이미 존재하는 `backend/app/schemas.py`의 보조 응답·요청 타입은 `src/types/server.ts`에 있습니다. 서버 파일은 수정하지 않았습니다. **서버와의 실제 통합 검증은 아직 하지 않았습니다.** 병렬 작업 후 대조할 항목은 [INTEGRATION.md](./INTEGRATION.md)에 기록했습니다.

## 검증

```sh
npm run build
npm test
npx playwright install chromium
npm run test:e2e
npm run format:check
```

Node 22.18 이상을 권장합니다. 단위 테스트는 Node 내장 테스트 러너와 TypeScript 타입 제거 기능을 사용합니다. 브라우저 테스트는 초대·외형·초상화 재생성·카드 원문·요청 재시도·스크롤 보존·엔딩 인용 이동·읽기 전용·모바일 레이아웃을 검증합니다.

## 상태 복원과 재시도

- 회차 생성·초상화 재생성도 요청 전에 `request_id`를 저장하며, 응답 유실과 새로고침 뒤 같은 ID로 재시도합니다. 새로 그리기를 명시적으로 요청하면 새 ID를 발급합니다.
- 미확정 회차는 서버의 `portrait_confirmed`와 `presets`로 초상화 확인 화면에 복원합니다. 과거 장면 그림은 `scenes` 응답으로 읽어 로컬 캐시가 없어도 복원합니다.
- 대화 제출 전에 `request_id`와 원문을 저장합니다. 실패 뒤 같은 요청을 재시도합니다. 페이지 재진입 시 서버에서 이미 완료된 턴을 확인하고 중복 소비하지 않습니다.
- 일반 입력과 카드 입력은 하나의 제출 잠금을 공유합니다. Enter 전송, Shift+Enter 줄바꿈, 한글 조합 중 Enter를 구분합니다.
- 카드 글자 수는 `Intl.Segmenter`의 grapheme 기준입니다. 띄어쓰기·줄바꿈·이모지를 그대로 보존합니다.
- 엔딩 본문 준비 중에는 마지막 대화를 유지합니다. 준비 완료 후 `결말 펼쳐보기`로 이동해, 위쪽 로그를 읽던 스크롤을 빼앗지 않습니다.
- 이미지 준비는 본문과 독립적으로 조회합니다. 30초가 지나면 안내 문구만 바뀝니다. 실패한 그림만 다시 만들 수 있습니다.
- 목 저장소와 UI 캐시는 `last-bookmark:` 접두사로 브라우저 localStorage에 저장합니다. 운영 서버의 보안을 대체하지 않습니다.

## 실패 상태 검수

개발 서버의 브라우저 콘솔에서 한 번 발생할 실패를 설정할 수 있습니다. 일반 화면에는 개발용 조작기를 노출하지 않습니다.

```js
const mock = await import("/src/api/mock-server.ts");
mock.setMockFault("turn-after-save");
```

| 이름                        | 다음 동작                              |
| --------------------------- | -------------------------------------- |
| `auth`, `list`              | 인증 또는 목록 조회 실패               |
| `portrait`                  | 초상화 첫 생성 실패                    |
| `portrait-after-save`       | 초상화 생성 완료 후 응답 유실          |
| `portrait-retry-after-save` | 초상화 재생성 완료 후 응답 유실        |
| `portrait-retry`            | 초상화 재생성 실패                     |
| `turn`                      | 저장 전 대화 실패                      |
| `turn-after-save`           | 저장은 완료했으나 응답 유실            |
| `end`                       | 조기 종료 실패                         |
| `ending-body`               | 엔딩 본문 준비 중                      |
| `scene-slow`                | 이야기 시작 시 장면 이미지를 36초 지연 |
| `image-slow`                | 12턴 종료 시 엔딩 이미지를 36초 지연   |
| `ending-image`              | 엔딩 이미지 생성 실패                  |
| `image-refused`             | 엔딩 이미지 생성 거부                  |

`setMockFault(name, 횟수)`로 반복 횟수도 정할 수 있습니다. 새로고침 시 주입한 실패는 초기화되지만 저장된 이야기와 이미지 작업 시각은 유지됩니다.
