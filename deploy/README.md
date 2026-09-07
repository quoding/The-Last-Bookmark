# 배포용 정적 빌드 — `frontend/dist`와 다른 폴더인 이유

`web`(nginx) 서비스는 `frontend/dist`가 아니라 이 폴더의 `deploy/dist/`를 서빙한다.

**이유:** Codex가 프론트 작업을 검증할 때 습관적으로 `npm run build`를 돌리는데, 이게
`frontend/dist`를 매번 mock 모드(`VITE_API_BASE_URL=mock://local`, `frontend/.env.local` 기본값)로
덮어쓴다. 예전에는 nginx가 그 폴더를 직접 서빙해서, Codex가 검증 빌드를 돌릴 때마다 실제
서비스가 mock 더미 데이터로 바뀌는 사고가 있었다.

**배포 빌드를 새로 만들려면** (코드가 바뀌었을 때):

```sh
cd frontend
rm -rf ../deploy/dist
VITE_API_BASE_URL=https://tainai.quoding.com npx vite build --outDir ../deploy/dist
cd ..
docker compose up -d --force-recreate web
```

`--force-recreate`가 필요한 이유: `deploy/nginx.conf`처럼 단일 파일을 볼륨 마운트하면
편집 도구가 원자적 치환(inode 교체)으로 저장할 때 컨테이너가 예전 inode를 계속 물고 있을 수
있다. `deploy/dist`는 디렉터리 마운트라 파일 개별 교체는 즉시 반영되지만, 빌드 결과물
전체가 바뀌었을 때는 확실히 하기 위해 재생성한다.

`deploy/dist/`는 `.gitignore` 대상이라 커밋되지 않는다. 서버를 새로 세팅할 때마다 위
명령으로 다시 만들어야 한다.
