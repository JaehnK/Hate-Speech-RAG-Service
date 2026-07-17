# Google 로그인 전 공개 샘플 Stitch 설계

## 현재 상태

OAuth/BYOK 설계 문서는 비로그인 방문자가 운영자 검토 공개 샘플 보고서를 열람하는 정책을 정의한다. 하지만 2026-07-17 확인 기준 실제 구현에는 다음이 없다.

- 비로그인 공개 샘플 랜딩/목록 route
- 공개 샘플 목록 API
- `report_snapshots.is_public_sample` 스키마와 운영자 지정 도구
- Google OAuth endpoint와 세션 UI

기존 `/`는 분석 입력 화면을 즉시 노출하며, 비로그인 샘플 경험과 권한 경계를 표현하지 않는다.

## Stitch 산출물

- Stitch project: `17186233821931043279` (`YouTube Hate Speech Analyzer`)
- design system: `assets/98fed8fa4ddc44e3a4f47d5b2513eb9a` (`VoxGuard`)
- desktop: `8ccfcefd4a8f4bac834624e573daf115` (`공개 랜딩 & 샘플 탐색 화면`)
- mobile: `8e616cd2ae9649ef9abbf3f9d3c47f44` (`공개 랜딩 & 샘플 탐색 화면 (모바일)`)

데스크톱은 기존 보고서와 같은 Deep Indigo/Crimson 토큰, Inter/JetBrains Mono, 4px grid, 저대비 outline을 사용한다. 모바일은 390px 기준 single column, 16px 좌우 여백, 44px 이상 touch target을 기준으로 한다.

## 사용자 흐름

1. 비로그인 방문자가 랜딩에 진입한다.
2. 축약 보고서 preview로 산출물의 형태를 파악한다.
3. `공개 샘플 보고서`에서 운영자가 검토한 실제 보고서를 연다.
4. RAG 방법과 해석 한계를 확인한다.
5. 새 분석을 원하는 경우에만 Google OAuth를 시작한다.
6. 로그인 후 본인 Anthropic/Upstage API key 등록으로 이동한다.

공개 샘플 열람은 로그인 또는 API key 등록을 요구하지 않는다. 새 job 생성은 로그인과 필수 BYOK 검증 이후에만 허용한다.

## 화면 계약

### 상단·히어로

- `공개 샘플`, `RAG 방법론`, `해석 원칙`
- `Google로 로그인`
- `로그인 전에, 분석 결과를 먼저 확인하세요`
- 전체 발화, 혐오표현 비율, 분포·network 축약 preview

### 공개 샘플 card

card는 API에서 받은 실제 공개 보고서만 표시한다.

- report ID·video ID
- YouTube thumbnail, 영상 제목, 채널명
- 분석 일자
- 댓글·답글 수집 수
- 자막 분석 가능 여부
- 혐오표현 비율
- 주요 한국어 category label
- `운영자 검토 공개본`
- `보고서 열기`

Stitch에 표시된 예시 제목·수치·thumbnail은 layout 참조용이다. 코드에 가짜 보고서로 고정하지 않는다.

### 방법·해석 경계

- 정의·유사 사례 이중 근거
- 댓글·자막 발화 단위 분석
- 상호작용 network
- `모델 판정은 법적 판단이나 개인의 성향·의도를 진단하는 결과가 아닙니다. 수집 가능한 공개 데이터와 명시된 분류 기준 안에서 해석해야 합니다.`

## 공개 표면 제약

- Swagger, OpenAPI, endpoint, 환경변수, provider key, 내부 model/collection 정보를 노출하지 않는다.
- 아직 제공하지 않는 약관·개인정보처리·지원 링크를 가짜로 만들지 않는다.
- 혐오표현 결과에만 Crimson을 사용한다.
- 공개 샘플 지정 전에 댓글 원문·작성자 표시·영상 metadata를 운영자가 검토한다.

## 후속 구현 순서

1. `report_snapshots.owner_user_id`, `is_public_sample`과 인증 스키마 migration
2. Google OAuth·session·BYOK backend 구현
3. 운영자 공개 샘플 지정/해제 도구
4. `GET /api/reports/public` 목록과 공개 report 상세 소유권 예외
5. Stitch desktop/mobile을 기준으로 public landing 구현
6. session 유무에 따라 public landing 또는 분석 workspace로 분기
7. 비로그인 public sample E2E, 비공개 report 차단, 로그인 redirect E2E

FastAPI에서 `/api/reports/public`은 `/{report_id}`보다 먼저 등록해 `public`이 UUID path parameter로 해석되지 않게 한다.

## 완료 기준

- 비로그인 방문자가 공개 샘플 목록과 상세를 열 수 있다.
- 비공개 report는 report ID를 알아도 비로그인·비소유자가 열 수 없다.
- 새 분석 CTA는 Google OAuth과 BYOK 완료 전에 job을 생성하지 않는다.
- 샘플 0건·loading·API 오류·3건 이상 layout이 desktop/mobile에서 구분된다.
- production bundle에 개발자 표면이 노출되지 않는다.
