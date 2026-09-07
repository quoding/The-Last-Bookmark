# AGENTS.md — 마지막 책갈피 (프론트엔드)

이 파일은 Codex가 이 저장소에서 작업할 때 따르는 지침이다. **작업 범위는 `frontend/`
안으로 한정한다.** `backend/`, `docs/`, `CLAUDE.md`는 읽기만 하고 수정하지 않는다 — 백엔드는
별도 도구(Claude Code)가 담당한다.

## 0. 먼저 읽을 것

작업 시작 전 아래 문서를 반드시 읽는다.

- `docs/story.md` — 세계관, 캐릭터 한서윤, 장면 의도, 엔딩 서사 규칙. **무엇을 만드는가**
- `docs/ui-spec.md` — 화면 구성, 턴별 시각 테이블, 카드 인터랙션. **어떻게 보이는가**
- `docs/api-contract.md` — 백엔드와의 유일한 접점. **원본은 여기다.** 요청·응답 형태를
  임의로 가정하지 않는다. 계약을 바꿔야 할 것 같으면(새 필드가 필요하다 등) 코드를 먼저
  고치지 말고 사용자에게 확인받는다
- `docs/ops-notes.md` — 백엔드·프론트 공통 운영 규칙(시크릿 관리, 배포 폴더 구조 등).
  `CLAUDE.md`도 같은 문서를 본다

문서가 충돌하면 서사와 캐릭터는 story.md, 화면 동작은 ui-spec.md, API 계약은
api-contract.md, 공통 운영 규칙은 ops-notes.md를 따른다.

## 1. 프로젝트 개요

폐점을 앞둔 독립서점에서 30분 동안 캐릭터와 대화하고, **플레이어가 실제로 한 말이 근거로
남는 결말과 일러스트**를 받는 한국어 인터랙티브 로맨스 웹 게임. 채용 포트폴리오용 데모이며
초대 코드를 가진 소수만 접속한다.

## 2. 작업 분담

- **Codex**: `frontend/` 전체 (React 18 + TypeScript + Vite, CSS Modules)
- **Claude Code**: `backend/`(FastAPI), LLM·이미지 연동, 배포 설정

프론트가 API 계약을 바꿔야 할 필요를 느끼면(예: 응답에 없는 필드가 필요하다) 직접 백엔드를
고치지 말고, `docs/api-contract.md` 기준으로 뭐가 부족한지 정리해 사용자에게 알린다.

## 3. 핵심 설계 원칙 (프론트 관점)

- **내부 수치 노출 금지**: `trust`/`closeness`/`tension` 같은 값은 API 응답 어디에도 없다.
  화면에서도 당연히 표시하지 않는다.
- **원문 보존**: 플레이어 입력, 카드 문장을 교정·요약·번역하지 않는다. 그대로 렌더링한다.
- **멱등성**: `docs/api-contract.md`에 명시된 요청은 매번 새 `request_id`를 생성해 붙인다.
  응답 유실·새로고침 뒤 같은 `request_id`로 재시도하면 서버가 원래 응답을 그대로 돌려준다.
- **장면 이미지는 미리 준비된다**: 회차 생성(초상화 성공) 직후부터 장면 1~4가 백그라운드로
  생성되기 시작한다. `/start` 응답이나 재진입 시 `image_url`이 `null`이면 스켈레톤을 보여주고
  `GET /api/sessions/{id}`를 폴링한다 — 장면 1도 예외 없이 같은 패턴을 따른다.
- **에러 메시지**: `POST /api/auth/verify`가 401/403/429를 주면, 서버가 담아 보낸 `detail`
  텍스트를 그대로 보여준다. 상태 코드별로 프론트가 별도의 문구를 새로 짓지 않는다.

## 4. 검증 방법

```sh
cd frontend
npm install
npm run build      # tsc + vite build. 기본 env(mock://local)로 frontend/dist에 생성됨
npm test           # 단위 테스트
npx playwright install chromium   # 최초 1회
npm run test:e2e   # 브라우저 회귀 테스트
npm run format:check
```

**`npm run build`의 결과물(`frontend/dist`)은 검증용이지 배포용이 아니다.** 운영 서버는
`deploy/dist`라는 별도 폴더를 서빙한다(자세한 내용은 `docs/ops-notes.md`). 이 둘을 헷갈리지
않는다 — `frontend/dist`를 실제 서비스에 반영하려고 직접 복사하거나 경로를 바꾸지 않는다.
배포는 Claude Code(백엔드/인프라 담당)가 처리한다.

## 5. 커밋

- git은 Codex가 아니라 별도 도구(Claude Code)가 관리한다. Codex는 git 명령을 실행하지 않는다
- 작업 기록은 `worklog_codex/`에 `yymmhhmm_worklog.md` 형식으로 남긴다. 이 폴더는
  gitignore 대상이라 커밋에는 안 들어가지만, 그래도 실제 API 키·비밀번호·IP 같은 값은
  적지 않는다(`docs/ops-notes.md` 참고)

## 6. 하지 말 것

- **git 명령을 직접 실행하지 않는다.** `git add`, `git commit`, `git push`, `git checkout`
  등 어떤 git 명령도 스스로 실행하지 않는다. 변경한 파일을 커밋할 준비가 됐으면 사용자에게
  알리기만 한다.
- `backend/`, `docs/`, `CLAUDE.md` 수정
- API 계약에 없는 필드를 임의로 가정해서 사용
- 내부 수치를 화면이나 로컬 상태에 노출
- 플레이어 입력·카드 문장 교정·요약·번역
- `frontend/dist` 빌드 결과를 배포 경로로 옮기거나 배포 설정을 건드리는 것
