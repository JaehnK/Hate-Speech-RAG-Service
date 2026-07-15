# Stitch 프론트엔드 구현 및 전달 기록

## 목적

Stitch의 `YouTube Hate Speech Analyzer` 프로젝트를 읽어 별도 Docker 서비스로 프론트엔드를 구현하고, 기존 FastAPI/worker/PostgreSQL 구성과 동일 출처 프록시로 연결한다.

## 구현 기준

- 작업 브랜치: `feat/stitch-frontend`
- Stitch 프로젝트: `projects/17186233821931043279`
- 디자인 시스템: `VoxGuard`
- 기준 화면:
  - `8fcf66da799a4813b6fc5a3cdafab629`: 분석 요청
  - `6585f0190b214edebc514c249fc3f1bc`: 작업 상태
  - `22d00c482582418d97dd190a2f8ae41b`: 분석 이력
  - `e01228e857184bcb8c055fea2287ed05`: 분석 보고서
- 제외 화면:
  - 로그인 화면은 사용자 인증 API가 없으므로 가짜 인증을 추가하지 않고 제외했다.

## 작업 시퀀스

1. Stitch MCP 연결과 소유 프로젝트 조회를 확인했다.
2. 프로젝트의 5개 화면, 원본 HTML, 스크린샷, VoxGuard 디자인 토큰을 검토했다.
3. FastAPI의 job, report, export 응답 구조와 실제 RAG pipeline step을 대조했다.
4. React, TypeScript, Vite 기반 SPA를 `frontend/`에 추가했다.
5. 분석 요청, 작업 polling, 브라우저 로컬 이력, 보고서, HTML/XLSX export를 실제 API에 연결했다.
6. 개발용 Vite 컨테이너와 배포용 unprivileged Nginx 컨테이너를 분리했다.
7. Compose에 독립 `frontend` 서비스를 추가하고 `/api`와 API 문서를 `web:8000`으로 프록시했다.
8. 프론트 단위 테스트, TypeScript 빌드, npm audit, Compose config를 검증했다.
9. fake pipeline으로 프론트 프록시를 통과하는 전체 job/report/export 흐름을 검증했다.
10. 읽기 전용 파일 시스템과 capability 제거 조건으로 배포 이미지를 기동해 SPA fallback, 보안 헤더, API 프록시를 검증했다.

## 화면과 API 연결

| 프론트 경로 | 기능 | 백엔드 API |
| --- | --- | --- |
| `/` | YouTube URL 또는 ID 분석 요청 | `POST /api/analysis-jobs` |
| `/jobs/{job_id}` | 2초 간격 작업 상태 polling | `GET /api/analysis-jobs/{job_id}` |
| `/history` | 이 브라우저에서 생성한 작업 재조회 | 저장된 job ID별 `GET /api/analysis-jobs/{job_id}` |
| `/reports/{report_id}` | 보고서 요약, 사례, 네트워크 표시 | `GET /api/reports/{report_id}` |
| 보고서 내보내기 | HTML 또는 XLSX 생성·다운로드 | report export 및 export status/download API |

분석 이력은 백엔드 목록 API가 없으므로 브라우저 `localStorage`에 최대 50개 job ID를 보관한다. 서버 데이터가 이 저장소보다 우선이며, 저장된 job을 찾을 수 없으면 이력에서 제외한다.

## Docker 구조

개발 환경의 프론트는 Vite HMR 서버이며 호스트 `3000`번을 사용한다. `/api`, `/health`, `/docs`, `/openapi.json`은 Docker 네트워크의 `web:8000`으로 전달한다.

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

접속 주소:

- 프론트: `http://localhost:3000`
- 백엔드 API 문서: `http://localhost:8000/docs`
- 프론트 프록시 API 문서: `http://localhost:3000/docs`

배포 후보 환경은 Nginx가 정적 SPA와 API reverse proxy를 함께 제공한다. 외부에 노출되는 기본 포트는 `3000`이고 FastAPI는 Compose 내부 네트워크에 유지된다.

```bash
APP_ENV=production PIPELINE_MODE=production ADMIN_TOKEN='<strong-token>' \
YOUTUBE_API_KEY='<key>' ANTHROPIC_API_KEY='<key>' UPSTAGE_API_KEY='<key>' \
docker compose -f compose.yaml -f compose.prod.yaml up --build -d
```

Windows SSH 터널로 프론트까지 접근하려면 SSH config에 다음 forward를 추가하고 재접속한다.

```sshconfig
LocalForward 3000 127.0.0.1:3000
LocalForward 8000 127.0.0.1:8000
```

## 검증 결과

- `npm run test`: 2 tests passed
- `npm run build`: TypeScript와 Vite production build 통과
- `npm audit`: 취약점 0건
- 개발 Compose frontend healthcheck: healthy
- 프론트 proxy readiness: `status=ok`
- fake E2E job: `succeeded`, progress 100%
- report API: `succeeded`
- HTML export 생성과 다운로드: 성공
- `/history`, `/jobs/{id}`, `/reports/{id}` 직접 접근: 모두 HTTP 200 및 SPA root 반환
- Nginx production image:
  - non-root image
  - read-only root filesystem
  - Linux capabilities 전체 제거
  - `/healthz`: HTTP 200
  - SPA fallback: HTTP 200
  - `/api/health/readiness` proxy: `status=ok`
  - CSP, frame, MIME sniffing, referrer 보안 헤더 확인

## 배포 전 제한사항

- 사용자 인증은 아직 제품 범위에 없으며 프론트에도 로그인 화면을 노출하지 않는다.
- 분석 이력은 서버 전체 목록이 아니라 현재 브라우저에서 요청한 작업만 표시한다.
- 실제 공개 배포 시 TLS ingress 또는 reverse proxy 앞단이 필요하다.
