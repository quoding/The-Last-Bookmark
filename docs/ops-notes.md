# 운영 공통 규칙 — 백엔드·프론트 둘 다 해당

`CLAUDE.md`(백엔드)와 `AGENTS.md`(프론트)가 공통으로 참조하는 문서다. 한쪽 작업에만
해당하지 않는, 저장소 전체에 걸친 규칙과 실제로 겪은 사고 기록을 담는다.

## 시크릿·비밀번호

- 초대 코드 평문, API 키, 관리자 비밀번호, IP 주소 같은 실제 값은 **`.env`(gitignore
  대상)에만 둔다.** `CLAUDE.md`, `AGENTS.md`, `docs/`, 커밋 메시지, `worklog_*` 어디에도
  실제 값을 적지 않는다.
- **이 저장소는 public이다.** 한번 커밋되면(그 커밋을 나중에 되돌려도) 히스토리에 영원히
  남는다 — 파일을 다시 고치는 것으로는 이미 커밋된 값이 사라지지 않는다.
- 실제로 있었던 사고: `CLAUDE.md`에 실제 초대 코드 평문이 적혀 있다가 유출됨 → 코드 자체를
  새 값으로 교체(rotate)해서 해결. 문서를 고치는 것만으로는 해결이 안 됐다는 점이 핵심.
- `worklog_claude/`, `worklog_codex/`는 gitignore 대상이다(추적 안 함). 그래도 작업 기록에
  실제 값을 적는 습관 자체를 들이지 않는다 — 나중에 실수로 다른 곳에 옮겨 적을 수 있다.

## 배포 폴더 — `frontend/dist` vs `deploy/dist`

**절대 헷갈리면 안 되는 부분.**

- `frontend/dist`: Codex가 프론트 작업 검증할 때 `npm run build`로 만드는 결과물. 기본
  env(`frontend/.env.local` = `mock://local`)로 빌드되며, **이건 로컬 검증용이지 배포용이
  아니다.**
- `deploy/dist`: 실제 운영 서버(nginx `web` 컨테이너)가 서빙하는 진짜 배포 폴더. 실제
  API 도메인(`VITE_API_BASE_URL=https://tainai.quoding.com`)으로 별도 빌드한다. 재배포
  절차는 `deploy/README.md` 참고.
- 실제로 있었던 사고: 예전엔 nginx가 `frontend/dist`를 직접 서빙했다. Codex가 평소처럼
  검증 빌드를 돌렸더니 그게 그대로 운영 서버를 mock 더미 데이터로 덮어써버렸다(로그인은
  아무 코드나 되고, 회차 목록에 가짜 이야기가 뜨는 상태가 됨). 그래서 폴더 자체를 분리해
  Codex가 `frontend/`에서 뭘 하든 운영에는 전혀 영향이 없게 고쳤다. **이 분리 구조를 다시
  합치거나 우회하지 않는다.**

## 커밋 규칙

- 한글 커밋 메시지, 기능 단위로 나눈다("여러 파일 수정" 같은 뭉뚱그린 커밋 금지)
- `worklog_claude/`, `worklog_codex/`에 작업 기록을 남기되(각자 자기 것만), 시크릿은
  절대 적지 않는다(위 항목 참고)
- 프론트 커밋은 `frontend/` 안에서만, 백엔드 커밋은 `backend/` 안에서만 — 서로의 영역은
  API 계약(`docs/api-contract.md`)을 바꿔야 할 때만, 그것도 사용자 확인 후에 건드린다

## nginx 설정 파일 편집 시 주의

`deploy/nginx.conf`처럼 docker-compose가 단일 파일로 볼륨 마운트한 설정은, 편집 도구가
원자적 치환(임시 파일 쓰고 rename, 즉 inode 교체) 방식으로 저장하면 컨테이너가 예전 inode를
계속 붙잡고 있어 변경이 반영 안 될 수 있다. `nginx -s reload`로 안 될 때는
`docker compose up -d --force-recreate web`으로 컨테이너 자체를 재생성한다.
