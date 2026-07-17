# Google OAuth, 세션, BYOK 상세 설계

| 항목 | 값 |
| --- | --- |
| 버전 | v0.1.0 |
| 작성일시 | 2026-07-16 22:00:00 KST |

## 문서 목적

이 문서는 `00_project_brief.md`, `01_user_scenarios.md`, `02_hld.md`, `03_data_model.md`, `05_api_spec.md`에서 범위로 확정한 Google OAuth 로그인, 세션 쿠키, 사용자 API 키(BYOK) 기능의 구현 상세를 정의한다.

이 문서는 구현자(코딩 에이전트 포함)가 쿠키 속성, 토큰 저장 방식, 암호화 방식을 임의로 선택하지 않도록 하는 기준 문서다. 다른 문서와 충돌하면 `03_data_model.md`(스키마)와 `05_api_spec.md`(API 표면)를 우선하고, 이 문서는 그 사이를 채우는 구현 세부 사양으로 취급한다.

## 범위

포함:

- Google OAuth Authorization Code flow(PKCE 포함)
- 세션 생성, 검증, 만료, 로그아웃
- 세션 쿠키 속성과 CSRF 대응
- 사용자 Anthropic/Upstage API 키 등록, 검증, 암호화 저장, 사용, 삭제
- 관련 환경변수와 오류 코드

제외(이 문서에서 다루지 않음):

- 이메일/비밀번호 로그인, Google 외 IdP
- 조직/팀 단위 권한 관리
- API 키 암호화 마스터 키의 자동 rotation(운영 중 수동 절차로만 남긴다)

## 핵심 결정

- 세션은 서버가 발급하는 opaque 랜덤 토큰을 기준으로 하며, 클라이언트가 payload를 직접 해석할 수 있는 JWT를 세션의 진실 공급원으로 사용하지 않는다.
- 세션 쿠키는 `HttpOnly` + `SameSite=Lax`를 기본으로 하고, 운영 환경에서는 `Secure`를 강제한다.
- Anthropic/Upstage API 키는 애플리케이션 레벨 대칭키 암호화(Fernet, AES-128-CBC+HMAC 기반) 후에만 DB에 저장한다.
- YouTube API 키는 이 문서의 대상이 아니다. 계속 운영자 공용 키(`secret_references`, 환경변수)로 관리한다.

## OAuth 로그인 흐름

### 1. 로그인 시작 — `GET /api/auth/google/login`

1. 서버가 CSRF 방지용 `state`(32바이트 랜덤, base64url)와 PKCE `code_verifier`/`code_challenge`(S256)를 생성한다.
2. `state`와 `code_verifier`를 단기 쿠키 `hsr_oauth_state`에 저장한다(아래 쿠키 표 참조).
3. 서버가 다음 파라미터로 Google authorization endpoint로 302 리디렉션한다.

```text
https://accounts.google.com/o/oauth2/v2/auth
  ?client_id=<GOOGLE_CLIENT_ID>
  &redirect_uri=<GOOGLE_OAUTH_REDIRECT_URI>
  &response_type=code
  &scope=openid email profile
  &state=<state>
  &code_challenge=<code_challenge>
  &code_challenge_method=S256
  &access_type=online
  &prompt=select_account
```

### 2. 콜백 처리 — `GET /api/auth/google/callback`

1. 요청의 `state` query 값과 `hsr_oauth_state` 쿠키에 저장된 `state`를 비교한다. 다르거나 쿠키가 없으면 `OAUTH_STATE_MISMATCH`로 실패 처리하고 로그인을 완료하지 않는다.
2. `hsr_oauth_state` 쿠키를 즉시 만료시킨다(1회용).
3. 서버가 Google token endpoint에 `code`, `code_verifier`, `client_id`, `client_secret`, `redirect_uri`로 code-token 교환을 요청한다(서버-투-서버 호출, 브라우저를 거치지 않는다).
4. 응답으로 받은 ID token을 검증한다: 서명(Google JWKS 기준), `aud == GOOGLE_CLIENT_ID`, `iss`가 `accounts.google.com` 또는 `https://accounts.google.com`, `exp` 유효.
5. ID token claim에서 `sub`, `email`, `email_verified`, `name`, `picture`를 추출한다.
6. `users.google_sub = sub`로 기존 사용자를 조회한다. 없으면 새 row를 만들고, 있으면 `email`, `display_name`, `avatar_url`, `last_login_at`을 갱신한다.
7. 새 세션을 발급한다(아래 "세션 발급" 참조).
8. 세션 쿠키를 `Set-Cookie`로 내려주고, 프론트엔드 홈 또는 로그인 시작 전 원래 경로로 302 리디렉션한다.

실패 처리:

- token 교환 실패, ID token 서명/claim 검증 실패, Google 오류 응답은 모두 `OAUTH_CALLBACK_FAILED`로 분류하고 세션을 만들지 않는다.
- 실패 시 사용자에게는 재시도 안내만 노출하고, Google 응답 원문이나 `client_secret`은 어떤 로그에도 남기지 않는다.

## 세션 쿠키 사양

| 속성 | 값 | 이유 |
| --- | --- | --- |
| Name | `hsr_session` | 서비스 식별 접두어로 다른 쿠키와 구분 |
| HttpOnly | `true` | JavaScript에서 접근 불가, XSS로 인한 탈취 방지 |
| Secure | 운영 환경 `true`, 로컬 개발(`http://localhost`)만 `false` 허용 | HTTPS 전송 강제. `SESSION_COOKIE_SECURE` 환경변수로 제어 |
| SameSite | `Lax` | OAuth 콜백이 top-level GET 리디렉션이므로 `Strict`면 콜백 직후 쿠키가 전송되지 않아 로그인이 깨진다. `Lax`는 이 경로를 허용하면서 대부분의 cross-site 요청은 차단한다 |
| Path | `/` | 애플리케이션 전체에서 사용 |
| Domain | 배포 도메인(`SESSION_COOKIE_DOMAIN`), 서브도메인 분리가 없으면 생략 | 프론트엔드와 백엔드가 같은 도메인/서브도메인 구조일 때만 명시 |
| Max-Age | `SESSION_TTL_SECONDS`(기본 1209600초 = 14일) | 세션 유효 기간의 상한 |

단기 보조 쿠키 `hsr_oauth_state`:

| 속성 | 값 |
| --- | --- |
| HttpOnly | `true` |
| Secure | `hsr_session`과 동일 정책 |
| SameSite | `Lax` |
| Max-Age | `600`(10분, OAuth 왕복 시간만 커버) |

### 세션 발급

1. 32바이트 이상의 암호학적으로 안전한 랜덤 값을 생성하고 base64url로 인코딩해 원문 세션 토큰으로 사용한다.
2. 원문 토큰을 SHA-256으로 해시해 `user_sessions.session_token_hash`에 저장한다. 원문 토큰 자체는 DB에 저장하지 않는다.
3. `expires_at = now + SESSION_TTL_SECONDS`, `created_at = now`, `last_seen_at = now`로 row를 만든다.
4. 원문 토큰만 `Set-Cookie: hsr_session=<원문 토큰>; ...`로 클라이언트에 내려준다.

### 세션 검증(요청마다)

1. `hsr_session` 쿠키에서 원문 토큰을 읽는다. 없으면 미인증으로 처리한다.
2. 원문 토큰을 SHA-256으로 해시해 `user_sessions`를 `session_token_hash`로 조회한다.
3. row가 없거나, `revoked_at`이 설정되어 있거나, `expires_at <= now`이면 미인증(`SESSION_EXPIRED` 또는 `SESSION_INVALID`)으로 처리하고 `401`을 반환한다.
4. 유효하면 `user_id`를 요청 컨텍스트에 주입하고, `users.status`가 `suspended`면 `403`을 반환한다.
5. sliding expiration: `expires_at`까지 남은 시간이 `SESSION_TTL_SECONDS`의 절반 미만이면 `expires_at`을 `now + SESSION_TTL_SECONDS`로 갱신하고 `last_seen_at`을 갱신한다. 이 경우 응답에도 갱신된 `Set-Cookie`를 함께 내려준다. 남은 시간이 충분하면 `last_seen_at`만 갱신하고 쿠키는 재발급하지 않는다.

### 로그아웃 — `POST /api/auth/logout`

1. 현재 세션의 `revoked_at = now`로 설정한다(하드 삭제하지 않고 감사 추적을 위해 남긴다).
2. `Set-Cookie: hsr_session=; Max-Age=0; ...`로 쿠키를 즉시 만료시킨다.
3. 다른 기기/브라우저에서 발급된 세션에는 영향을 주지 않는다(기기별 세션 row가 분리되어 있으므로).

## CSRF 대응

`SameSite=Lax` 쿠키는 cross-site `POST`/`PUT`/`DELETE` 요청에 쿠키를 첨부하지 않으므로 고전적인 form 기반 CSRF는 기본적으로 차단된다. 다만 다음을 추가로 적용한다.

- 상태를 변경하는 모든 API(`POST`, `PUT`, `DELETE`)는 요청의 `Origin` 헤더가 허용된 프론트엔드 origin과 일치하는지 검증한다. 불일치하면 `403`을 반환한다.
- 프론트엔드는 모든 API 호출에 커스텀 헤더(예: `X-Requested-With: hatespeechraw`)를 추가한다. 브라우저는 단순 HTML form 제출로는 커스텀 헤더를 보낼 수 없으므로, 이 헤더가 없는 상태 변경 요청은 거부한다.
- 프론트엔드와 백엔드가 서로 다른 origin(예: 별도 서브도메인)에 배포되는 경우, CORS는 정확한 origin 목록으로 허용하고 `credentials: true`로 설정한다. 와일드카드 origin은 쿠키 인증과 함께 사용할 수 없으므로 금지한다.

## BYOK API 키 등록 흐름

1. 로그인한 사용자가 `PUT /api/me/api-keys/{provider}`로 API 키 원문을 전송한다(HTTPS 전송, 요청 본문은 로그에 남기지 않는다).
2. 서버가 저장 전에 provider별 최소 비용 검증 호출을 수행한다.
   - Anthropic: 모델 목록 조회처럼 과금이 없거나 최소한인 endpoint를 우선 사용한다. 불가능하면 `max_tokens`를 최소로 설정한 호출로 대체한다.
   - Upstage: 계정/모델 조회 endpoint가 있으면 우선 사용하고, 없으면 최소 길이 텍스트로 임베딩 1회 호출한다.
3. 검증에 실패하면 키를 저장하지 않고 `422`(`API_KEY_INVALID`)를 반환한다. 실패 사유는 마스킹해서 `last_validation_error`에 남긴다.
4. 검증에 성공하면 키를 암호화해 저장하고, `key_fingerprint`(예: 키 뒷 4자리)를 계산해 함께 저장한다. 원문 키는 이 시점 이후 애플리케이션 메모리에서 즉시 폐기한다(참조를 유지하지 않는다).
5. 같은 `(user_id, provider)` row가 이미 있으면 갱신(대체)한다.

### 분석 job 실행 시 키 사용

1. `POST /api/analysis-jobs` 처리 시 API 레이어는 `user_api_keys`의 `is_valid` 여부만 확인하고, 복호화는 하지 않는다.
2. worker가 job을 실행할 때, job의 `user_id`로 필요한 provider 키를 조회하고 그 순간에만 복호화해 LLM/embedding 클라이언트에 주입한다.
3. 복호화된 키는 해당 job의 실행 스코프 안에서만 메모리에 보관하고, job 종료 후 참조를 유지하지 않는다.
4. 복호화된 키 원문은 `operation_logs`, `comment_analysis_results.raw_response`, Langfuse trace, 예외 메시지를 포함한 어떤 영속 저장소에도 기록하지 않는다. 예외 처리 시에는 원문 키가 포함될 수 있는 SDK 예외 메시지를 그대로 저장하지 않고, provider와 오류 유형만 마스킹해서 남긴다.
5. provider 호출이 인증 오류(401/403 계열)로 실패하면 해당 job step을 `API_KEY_INVALID`로 실패 처리하고, `user_api_keys.is_valid`를 `false`로 갱신한다.

## API 키 암호화 설계

- 암호화 방식: `cryptography` 패키지의 Fernet(AES-128-CBC + HMAC-SHA256, 버전/타임스탬프/IV/인증 태그를 자체 포함)을 사용한다. IV 생성과 인증 태그 검증을 라이브러리가 처리하므로 구현 실수 여지가 적다.
- 마스터 키: `API_KEY_ENCRYPTION_KEY` 환경변수에 32바이트를 base64로 인코딩해 보관한다. `openssl rand -base64 32` 등으로 1회 생성하고, 소스 저장소에는 절대 커밋하지 않는다(`.env.example`에는 플레이스홀더만 남긴다).
- 저장 형식: `user_api_keys.encrypted_key`에는 Fernet 토큰(bytes)을 그대로 저장한다. 복호화는 같은 `API_KEY_ENCRYPTION_KEY`로만 가능하다.
- 알려진 한계(MVP 범위): 마스터 키는 단일 서버 보유 키이며 KMS 연동이나 자동 rotation은 하지 않는다. 마스터 키를 교체하면 기존 `encrypted_key` row는 모두 복호화 불가능해지므로, 교체 시 전체 사용자에게 API 키 재등록을 요구하는 마이그레이션 절차가 필요하다. 이 절차는 운영 문서에서 별도로 정의한다.

## 오류 코드

| 코드 | 상황 | HTTP status |
| --- | --- | --- |
| `OAUTH_STATE_MISMATCH` | 콜백의 state가 쿠키와 불일치 | `400` |
| `OAUTH_CALLBACK_FAILED` | code-token 교환 또는 ID token 검증 실패 | `400` |
| `SESSION_INVALID` | 세션 쿠키 없음 또는 알 수 없는 토큰 | `401` |
| `SESSION_EXPIRED` | 세션 만료 또는 revoke됨 | `401` |
| `ACCOUNT_SUSPENDED` | `users.status = 'suspended'` | `403` |
| `API_KEY_NOT_CONFIGURED` | 필요한 provider 키 미등록 | `422` |
| `API_KEY_INVALID` | 등록 시 검증 실패 또는 실행 중 인증 오류로 무효화됨 | `422` |
| `API_KEY_VALIDATION_FAILED` | provider에 일시적으로 연결할 수 없어 검증 자체를 완료하지 못함 | `503` |

## 환경변수

| 이름 | 설명 | 비고 |
| --- | --- | --- |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | 절대 로그 금지 |
| `GOOGLE_OAUTH_REDIRECT_URI` | 콜백 URL, Google Cloud Console에 등록된 값과 정확히 일치해야 함 | |
| `SESSION_COOKIE_NAME` | 기본 `hsr_session` | |
| `SESSION_COOKIE_DOMAIN` | 세션 쿠키 Domain 속성 | 서브도메인 분리 시에만 설정 |
| `SESSION_COOKIE_SECURE` | 기본 `true`, 로컬 개발만 `false` | |
| `SESSION_TTL_SECONDS` | 기본 `1209600`(14일) | |
| `API_KEY_ENCRYPTION_KEY` | Fernet 마스터 키(base64, 32바이트) | 절대 로그/커밋 금지 |

## 보안 체크리스트

- [ ] `hsr_session`, `hsr_oauth_state` 쿠키에 `HttpOnly` 적용
- [ ] 운영 환경에서 `Secure` 적용(HTTPS 강제)
- [ ] `SameSite=Lax` 적용, 프론트/백엔드가 다른 origin이면 CORS를 명시적 origin 목록 + `credentials: true`로 제한
- [ ] 세션 토큰은 DB에 해시만 저장, 원문은 응답 Set-Cookie 외 어디에도 기록하지 않음
- [ ] API 키 원문은 로그/오류 메시지/Langfuse trace/예외 스택트레이스 어디에도 남기지 않음
- [ ] API 키는 Fernet 암호화 후 저장, 마스터 키는 코드/저장소 밖에서만 관리
- [ ] 상태 변경 API에 Origin 검증 및 커스텀 헤더 체크 적용
- [ ] 관리자 인증(`X-Admin-Token`)과 사용자 세션 인증 경로를 분리 유지

## 구현 순서 제안

1. `03_data_model.md`의 `users`, `user_sessions`, `user_api_keys` 테이블과 `analysis_jobs.user_id`, `report_snapshots.owner_user_id`/`is_public_sample` 컬럼에 대한 Alembic 마이그레이션 작성
2. `KeyEncryptionService`(Fernet encrypt/decrypt 래퍼) 구현과 단위 테스트(테스트 전용 키 사용)
3. `GoogleOAuthClient`(로그인 URL 생성, code-token 교환, ID token 검증) 구현. 외부 호출은 인터페이스로 분리해 fake로 테스트 가능하게 함
4. `SessionService` + `SessionCookieCodec`(세션 발급/검증/만료/로그아웃) 구현
5. `auth_api` 라우터 연결: `/api/auth/google/login`, `/api/auth/google/callback`, `/api/auth/session`, `/api/auth/logout`, 그리고 다른 라우터에서 재사용할 `get_current_user` FastAPI dependency 작성
6. `UserApiKeyService` + provider별 검증 호출 구현, `/api/me/api-keys` 엔드포인트 연결
7. `POST /api/analysis-jobs`에 로그인/키 등록 검사 추가, job/report GET 계열에 소유권 검사 추가
8. worker에서 job 실행 시점에 사용자 키를 조회·복호화해 LLM/embedding 클라이언트에 주입하도록 변경(기존 전역 env var 키 사용 경로 대체)
9. 운영자가 특정 `report_snapshots.is_public_sample`을 `true`로 지정하는 관리자 명령/스크립트 작성(공개 샘플 보고서 노출용)
10. 프론트엔드: 로그인 버튼, OAuth 콜백 이후 리디렉션 처리, API 키 등록/삭제 화면, "내 리포트" 목록 화면(세션 없으면 로그인 유도, 공개 샘플은 비로그인으로도 노출)

## 보류 사항

- 세션을 PostgreSQL에 유지할지, 조회 부하가 커지면 Redis 등 별도 store로 옮길지
- `API_KEY_ENCRYPTION_KEY` rotation 및 KMS 연동 절차의 구체적 설계
- 프론트엔드/백엔드가 서로 다른 도메인에 배포될 경우 `SESSION_COOKIE_DOMAIN`과 CORS 설정의 정확한 값

## 검증 기준

이 설계는 다음 조건을 만족해야 한다.

- 로그인하지 않은 요청은 인증이 필요한 모든 endpoint에서 `401`을 받는다.
- 세션 쿠키 없이 세션 토큰을 알아낼 방법이 없다(DB에는 해시만 저장).
- API 키 원문이 등록 이후 어떤 응답, 로그, trace에도 나타나지 않는다.
- 로그아웃 이후 동일 세션 쿠키로는 인증된 요청을 수행할 수 없다.
- 다른 사용자의 job/report ID를 알아도 소유자가 아니면 조회할 수 없다(공개 샘플 제외).
- 마스터 키(`API_KEY_ENCRYPTION_KEY`)가 유출되지 않는 한, DB만 유출되어도 사용자 API 키 원문을 복원할 수 없다.
