# HateScope 메인 화면·공개 샘플 제공 작업

## 작업 계약

| 항목 | 값 |
| --- | --- |
| 작업일 | 2026-07-17 |
| 구현 브랜치 | `feat/hatescope-home-public-sample` |
| 대상 계정 | `lecielgris1@gmail.com` |
| 대상 영상 | `hIwABxM30Ds` |
| 신규 job | `3c320950-4ba1-4ff3-8b90-0ed4bd70eae3` |

사용자의 “`/anayze` 프론트를 메인 페이지로” 요청은 기존 `/analyze`의 분석 요청 UI를 `/`에 배치하고, 공개 샘플 랜딩은 `/samples`에서 계속 제공하는 것으로 해석했다. 기존 북마크를 깨지 않기 위해 `/analyze`는 `/`로 리다이렉트한다.

## 구현 순서

1. 실행 중인 job이 없고 대상 계정의 Anthropic·Upstage 키가 모두 유효한지 DB metadata만 확인했다. 키 평문은 조회하거나 출력하지 않았다.
2. 기존 성공 보고서와 같은 영상으로 새 job을 생성했다. worker는 job의 `user_id`로 소유자 키를 선택하고, 실행 시점에만 복호화한다.
3. 분석 화면을 `/`로 이동하고 `/samples`를 공개 샘플 전용 route로 분리했다.
4. 비로그인 사용자는 분석 UI를 볼 수 있지만 제출 시 Google OAuth로 이동한다. 로그인 후 기본 복귀 경로도 `/`로 맞췄다.
5. `/samples`는 세션을 조회해 비로그인에는 Google 로그인, 로그인에는 `display_name`(없으면 email)과 설정·로그아웃을 표시한다.
6. 사용자 노출 브랜드, HTML title, frontend package 이름을 `HateScope`로 변경했다.
7. 새 분석이 완료되면 그 결과만 `is_public_sample=true`로 지정하고 공개 목록·비로그인 상세 조회를 확인한다.

## 호환성 경계

- 변경: 화면 브랜드, HTML title, frontend package name, frontend route, OAuth 기본 복귀 경로.
- 유지: `hsr_session` 쿠키, `X-Requested-With: hatespeechraw`, DB schema/table, Docker Compose project·volume·container 식별자.

유지 항목은 사용자에게 보이는 브랜드가 아니라 기존 세션, CSRF 계약, 영속 볼륨과 배포 호환성을 보장하는 내부 식별자다. 이를 한 번에 바꾸면 활성 세션 만료나 데이터 볼륨 분리가 생길 수 있어 이번 범위에서 제외했다.

## 검증 기준

- frontend unit test와 production build가 통과한다.
- OAuth callback 기본 복귀 경로 backend test가 `/` 계약으로 통과한다.
- source와 build metadata에 `SENTINEL-YT`/`sentinel-yt`가 남지 않는다.
- 새 job이 terminal success 상태이며 report가 생성된다.
- 새 report가 공개 목록에 한 번 노출되고 비로그인 API로 조회된다.
- dev/test/prod Compose rendering과 backend 전체 test가 통과한다.

## 실행 결과

| 항목 | 결과 |
| --- | --- |
| job 상태 | `succeeded` |
| 실행 시간 | 26분 8초 |
| report ID | `d4484345-b69d-492e-88c5-a4330a3111e2` |
| 댓글 RAG | 709건 중 708 성공, 1 실패(99.86% 성공) |
| 댓글 실패 코드 | `LLM_OUTPUT_INVALID` 1건 |
| 자막 RAG | 107건 중 107 성공 |
| 댓글 네트워크 | `succeeded`, node 613개, edge 123개 |
| 탐지 혐오 댓글 | 335건 |
| 공개 상태 | 신규 report만 `is_public_sample=true` |

기존 report `e496f83a-014a-43e2-b017-5865aeac16b7`는 비공개로 유지했다. 새 report를 관리자 API로 승격한 뒤 인증 쿠키 없이 아래를 확인했다.

- `GET /api/reports/public`: 전체 1건이며 신규 report가 정확히 1회 포함
- `GET /api/reports/d4484345-b69d-492e-88c5-a4330a3111e2`: HTTP 200
- 공개 report의 comments, script-segments, network endpoint: 모두 HTTP 200
- report 집계: 댓글 709건, 댓글 분석 성공 708건·실패 1건, 자막 성공 107건

## 병합 전 검증

- frontend: 7 files, 17 tests 통과
- frontend production build: TypeScript와 Vite build 통과
- OAuth/BYOK 집중 backend: 3 tests 통과
- backend 전체 suite: exit 0, pytest node 112개 수집, `lastfailed=0`
- Ruff와 `compileall`: 통과
- dev/test/prod Compose config: 통과
- `git diff --check`: 통과

## 로컬 실행 반영

병합 후 web/frontend를 함께 bake하는 과정에서 Docker Buildx가 image export 단계에서 3분 이상 진전 없이 대기했다. 실행 중인 DB·worker에는 영향이 없었고, bake만 정상 중단했다. 이번 변경에는 새 runtime dependency가 없고 개발 Compose는 source bind mount를 사용하므로 다음 순서로 복구했다.

1. 로컬에 남아 있던 직전 정상 frontend development image(`npm run dev`, `/app`)를 기존 service tag로 복원했다.
2. `compose.yaml + compose.dev.yaml`을 명시해 web/frontend만 재생성했다.
3. frontend 3000, web 8000 host port와 두 healthcheck를 확인했다.
4. 실제 frontend origin에서 `/`, `/samples`, 공개 목록, 신규 공개 report 상세를 비로그인 상태로 호출했다.

최종 runtime 확인 결과:

- frontend, web, postgres: healthy
- worker: running
- `/`, `/samples`: HTTP 200, HTML title `HateScope`
- 비로그인 `GET /api/auth/session`: HTTP 401
- 비로그인 공개 목록: HTTP 200, 신규 sample 1건
- 비로그인 신규 report 상세: HTTP 200

production frontend 산출물 자체는 `npm run build`로 TypeScript와 Vite build를 통과했다. Docker exporter 지연은 애플리케이션 build 실패가 아니라 로컬 Docker image export 상태로 분리 기록하며, 배포 환경의 clean builder에서 production image bake를 다시 수행한다.
