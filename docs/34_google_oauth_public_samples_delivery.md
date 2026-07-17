# Google OAuth · BYOK · 로그인 전 공개 샘플 구현 기록

| 항목 | 값 |
| --- | --- |
| 구현 브랜치 | `feat/google-oauth-public-samples` |
| 기준 설계 | `30_auth_oauth_byok.md`, `33_prelogin_public_samples_stitch.md` |
| 구현일 | 2026-07-17 KST |

## 완료 범위

- Google Authorization Code + PKCE 로그인과 서명된 10분 OAuth state 쿠키
- 해시만 DB에 저장하는 opaque 세션, sliding expiration, 로그아웃 revoke
- Anthropic/Upstage 키의 사전 검증, Fernet 암호화 저장, fingerprint 조회·삭제
- 사용자 소유 job/report/export 접근 제어와 `/api/me/jobs`, `/api/me/reports`
- worker의 job별 키 복호화 및 RAG runtime 주입
- provider가 키를 401/403으로 거부하면 RAG 단계를 `API_KEY_INVALID`로 중단하고 저장 키를 무효화
- 관리자 토큰 기반 공개 샘플 지정·해제와 비로그인 공개 목록/상세 조회
- Stitch desktop/mobile 산출물을 기준으로 한 `/samples` 공개 랜딩, 실제 공개 보고서 card, 빈 목록·오류 상태
- 분석 요청 UI는 공개하고, 로그인과 필수 키가 모두 준비된 경우에만 실제 분석 요청 허용
- 브라우저 local storage 대신 계정 소유 job을 사용하는 분석 이력

## 요청 흐름

1. `/samples` 방문자는 로그인 없이 `GET /api/reports/public`의 운영자 검토 보고서를 확인한다.
2. 새 분석 CTA는 분석 메인 `/`로 이동하고, 비로그인 제출 시 `GET /api/auth/google/login?return_to=/`로 이동한다.
3. callback은 Google ID token을 검증하고 `hsr_session` HttpOnly 쿠키를 발급한다.
4. `/settings`에서 Anthropic/Upstage 키를 각각 검증·암호화 저장한다.
5. `POST /api/analysis-jobs`는 세션, CSRF header/origin, 두 키의 유효 상태를 확인하고 `user_id`를 기록한다.
6. worker는 해당 job의 키만 복호화해 job 전용 RAG runtime을 생성한다. job 큐는 기존 비동기 경계를 유지하며, RAG 항목 병렬 처리는 runtime 내부 concurrency 설정을 따른다.
7. report snapshot은 job 소유자를 상속한다. 운영자가 공개로 지정한 report만 인증 예외를 적용한다.

## 공개 샘플 운영 절차

댓글 원문, 작성자 표시, 영상 metadata와 공개 적합성을 사람이 검토한 뒤에만 실행한다.

```bash
curl -X PUT \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  http://localhost:8000/api/admin/reports/<REPORT_ID>/public-sample
```

공개 해제는 같은 경로에 `DELETE`를 사용한다. 공개 여부 변경은 원본 분석 결과를 수정하지 않는다.

## 배포 설정

필수 secret/config:

- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI` — 외부 frontend origin의 `/api/auth/google/callback`
- `FRONTEND_ORIGIN` — CSRF Origin 검증에 사용하는 정확한 origin
- `API_KEY_ENCRYPTION_KEY` — `Fernet.generate_key()`와 호환되는 URL-safe base64 키
- `SESSION_COOKIE_SECURE=true` — production HTTPS
- `SESSION_COOKIE_DOMAIN` — 별도 설정이 필요한 도메인 구성에서만 사용
- 서버 공용 `YOUTUBE_API_KEY`

로컬 Docker 기본 callback은 `http://localhost:3000/api/auth/google/callback`이다. frontend reverse proxy가 `/api`를 web container로 전달하므로 callback 이후 분석 메인 `/`로 정상 복귀한다. 기존 `/analyze`는 `/`로 호환 리다이렉트한다. Google Cloud Console의 승인된 redirect URI와 글자 단위로 같아야 한다.

사용자 Anthropic/Upstage 키는 환경변수에 넣지 않는다. 기존 전역 키는 인증 기능이 설정되지 않은 개발/legacy job 호환 경로에만 남겨 두었다. production에서는 OAuth/BYOK 설정을 필수로 검증한다.

## 보안 경계

- 상태 변경 사용자 API는 `Origin == FRONTEND_ORIGIN`과 `X-Requested-With: hatespeechraw`를 모두 요구한다.
- 세션 원문과 API 키 원문은 응답 payload, operation log, 분석 result에 기록하지 않는다.
- 비공개 report와 연결된 export는 소유자만 상태 조회·다운로드할 수 있다.
- 공개 sample은 report 상세·댓글·자막·network·기존 export 읽기에만 인증 예외가 적용된다. 새 export 생성은 report 소유자 인증과 CSRF 검사를 요구한다.
- Swagger/ReDoc/OpenAPI는 production에서 설정값과 관계없이 비활성화된다.

## 작업 시퀀스와 정합성 확인

1. 기존 설계 문서의 schema/API/error/cookie 결정을 대조했다.
2. 사용자·세션·키·소유권 schema와 Alembic migration을 작성했다.
3. OAuth/session/BYOK 서비스와 API를 연결했다.
4. job/report/export 소유권과 공개 sample 예외를 동일한 정책으로 연결했다.
5. worker를 job별 RAG runtime factory로 바꾸고 내부 RAG 병렬 설정은 유지했다.
6. Stitch 산출물의 실제-data-only 원칙으로 public frontend를 구현했다.
7. SQLite upgrade/downgrade, OAuth fake E2E, CSRF, 암호문 저장, 소유권, 공개 전환을 자동 검증했다.
8. 전체 backend/frontend test, lint, build, Compose config와 image build를 merge 전에 다시 수행한다.

## 운영 전 수동 검증

자동 테스트는 Google provider를 fake로 대체한다. 실제 배포 origin에서 아래 항목은 1회 수동 검증해야 한다.

- Google consent → callback → 분석 메인 `/` 복귀
- production `Secure` 세션 쿠키 발급
- 실제 Anthropic/Upstage 키 검증 및 짧은 분석 1건
- 다른 브라우저에서 비공개 report 차단, 공개 sample 열람

## Google production 공개 전 확인

Google 공식 web-server OAuth 문서 기준으로 production redirect URI는 HTTPS여야 하며(localhost만 예외), Cloud Console 등록값과 scheme·host·port·path·trailing slash까지 정확히 일치해야 한다. 현재 구현은 authorization code를 backend callback에서 즉시 교환한 뒤 query에 code가 없는 frontend route로 다시 보낸다.

OAuth 앱을 Testing이 아닌 외부 production 상태로 공개할 때는 소유 도메인의 공개 홈페이지와 실제 개인정보처리방침·이용약관 URL, 도메인 확인이 추가로 필요하다. 운영자 법적 명칭·연락처·보유 기간이 확정되지 않았으므로 이 저장소에는 임의 문구나 가짜 링크를 만들지 않았다. 해당 정보 확정은 배포 인프라/동의 화면 설정 단계의 차단 항목으로 관리한다.

- Web server OAuth: https://developers.google.com/identity/protocols/oauth2/web-server
- OAuth policy: https://developers.google.com/identity/protocols/oauth2/policies

## 의존성 보안 예외 — ChromaDB

2026-07-17 `pip-audit`는 `chromadb 1.5.9`에 `PYSEC-2026-311`(`CVE-2026-45829`)을 보고했다. advisory 기준 1.0.0부터 최신 1.5.9까지 영향 범위이며 아직 수정 버전이 없다. 취약 경로는 Chroma HTTP server의 collection 생성 API로 공격자가 `trust_remote_code=true`와 악성 model repository를 전달하는 경우다.

이 서비스는 Chroma server를 실행하거나 port/API를 노출하지 않고 `chromadb.PersistentClient`만 process 내부에서 사용한다. corpus 쓰기는 별도 tools profile과 운영자 명령으로만 실행하고, web은 vector volume을 read-only로 mount한다. 따라서 현재 배포 구조에서는 해당 네트워크 공격 경로가 노출되지 않는다.

결정:

- 수정 release가 나오기 전까지 embedded-only 구성을 유지하고 Chroma HTTP server를 추가하지 않는다.
- dependency audit는 `uv run pip-audit --ignore-vuln PYSEC-2026-311`로 다른 취약점이 0건인지 확인한다.
- 수정 release가 발표되면 lock 갱신, corpus/query 회귀 테스트 후 예외를 제거한다.
- Chroma server mode가 필요해지면 이 예외를 재사용하지 않고 인증·network isolation·취약 버전 차단을 새로 검토한다.

Advisory: https://github.com/pypa/advisory-database/blob/main/vulns/chromadb/PYSEC-2026-311.yaml

## Merge 전 최종 검증 결과

2026-07-17 `feat/google-oauth-public-samples` 커밋 상태에서 확인했다.

- backend: `108 passed, 1 skipped`
- frontend: `13 passed`, TypeScript/Vite production build 성공
- Ruff, Python `compileall`, `git diff --check`: 성공
- Alembic: single head `e7a4c10d4f82`, SQLite upgrade/downgrade test 성공
- Compose: dev/test/prod config 검증 성공
- Docker: production `web`, `worker`, `frontend` 이미지 빌드 성공
- dependency audit: `PYSEC-2026-311` embedded-only 예외를 제외한 알려진 취약점 0건
- 실제 Google OAuth: 구현 merge 시점에는 필수 local secret이 없어 자동 fake E2E까지만 완료

## 로컬 OAuth 설정 주입 후 검증

2026-07-17 `chore/oauth-live-config-validation`에서 사용자가 로컬 Google OAuth credential을 주입한 뒤 값 자체를 출력하지 않고 다음을 확인했다.

1. `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`의 설정 여부를 확인했다.
2. redirect URI가 `http://localhost:3000/api/auth/google/callback`과 정확히 일치하는지 확인했다.
3. 처음 입력된 `API_KEY_ENCRYPTION_KEY`가 Fernet 형식이 아닌 것을 감지하고 새 Fernet 키로 교체했다. 키 값은 command output과 문서에 남기지 않았다.
4. dev `frontend`, `web`, `worker` 이미지를 다시 빌드하고 migrate를 실행했다. 이전 web 이미지에서 발생했던 `cryptography`, `google.auth` import 실패는 새 의존성이 포함된 이미지로 교체한 뒤 해소됐다.
5. frontend/web health가 모두 200이고 DB가 Alembic head `e7a4c10d4f82`인지 확인했다.
6. `/api/auth/google/login`이 Google Accounts로 302 응답하고 OAuth state HttpOnly 쿠키를 발급하는지 확인했다.
7. Google authorize 페이지가 200으로 열리며 `invalid_client` 또는 등록되지 않은 OAuth client 오류가 없는지 확인했다.
8. 비로그인 `/api/me/jobs`, `/api/me/reports`, `/api/me/api-keys`가 401이고, 유효한 분석 요청 body를 사용한 비로그인 `POST /api/analysis-jobs`가 CSRF 경계에서 403인지 확인했다.
9. state/code 없는 callback이 400인지 확인하고, `/api/reports/public`이 200으로 응답하는지 확인했다.

검증 당시 공개 sample은 0건이었다. API 실패가 아니라 아직 운영자가 공개로 승인한 report가 없다는 의미이며, 로그인 전 화면은 정의된 empty state를 표시한다.

Google 계정 동의, 실제 authorization code 교환, 로그인 세션 발급은 사용자 브라우저 상호작용이 필요하므로 자동 HTTP 점검 범위에 포함하지 않는다. 로컬 브라우저에서 로그인한 뒤 `/api/auth/session`, `/settings`의 실제 Anthropic/Upstage 키 검증, 짧은 분석 1건을 순서대로 확인하면 local live E2E가 완결된다.

회귀 검증 결과:

- OAuth/BYOK, production 설정, app health, worker BYOK backend 테스트: `15 passed`
- frontend 테스트: `13 passed`
- frontend TypeScript/Vite production build: 성공
- Ruff와 `git diff --check`: 성공
