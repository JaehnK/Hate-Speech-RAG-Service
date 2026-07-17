# 공개 개발 표면 비노출

## 목적

서비스 이용자에게 필요하지 않은 API schema와 RAG 내부 구현 정보를 public HTTP surface에서 제거한다. 내부 문서와 source는 개발·감사를 위해 저장소에 유지한다.

## 노출 정책

| 표면 | development/test | production |
| --- | --- | --- |
| Swagger `/docs` | `API_DOCS_ENABLED=true`일 때만 노출 | 항상 404 |
| ReDoc `/redoc` | `API_DOCS_ENABLED=true`일 때만 노출 | 항상 404 |
| OpenAPI `/openapi.json` | `API_DOCS_ENABLED=true`일 때만 노출 | 항상 404 |
| `/rag-methodology` | public route 없음 | public route 없음 |
| readiness | orchestration endpoint 유지 | frontend 링크 없음 |

`API_DOCS_ENABLED` 기본값은 `false`다. `APP_ENV=production`이면 이 값을 `true`로 잘못 설정해도 FastAPI 문서 route를 만들지 않는다.

## 프론트엔드 제거 범위

- desktop/mobile header의 RAG 방법론 및 API 문서 링크
- sidebar의 RAG 방법론, readiness 및 API 문서 링크
- React Router의 `/rag-methodology` route

직접 `/rag-methodology`를 요청하면 SPA fallback 뒤 등록되지 않은 경로 처리에 따라 `/`로 이동한다. `RagMethodologyPage.tsx`와 재현성 문서는 public bundle의 진입점에서 참조하지 않으며 내부 개발 자료로만 유지한다.

## 검증 순서

1. 기본 설정에서 `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect`가 404인지 확인한다.
2. 개발 설정에서 `API_DOCS_ENABLED=true`일 때만 Swagger/ReDoc과 문서 전용 CSP가 동작하는지 확인한다.
3. production 설정에서는 `API_DOCS_ENABLED=true`를 주어도 세 문서 경로가 404인지 확인한다.
4. frontend navigation에 RAG 방법론, API 문서, readiness 링크가 없는지 테스트한다.
5. production frontend bundle에 prompt version, collection 이름, 내부 model ID 같은 RAG 개발 문자열이 포함되지 않는지 검사한다.
6. backend/frontend 전체 회귀 테스트와 production build를 통과시킨 뒤 병합한다.

## 검증 결과

- 기본 및 production 강제 비노출 API 테스트 통과
- backend: 101 passed, 1 skipped
- frontend: 12 passed
- frontend production build 통과
- production bundle 개발 문자열 검사 통과
- 실행 중인 backend에서 `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect` 모두 404 확인
- backend `/health` 정상 확인
