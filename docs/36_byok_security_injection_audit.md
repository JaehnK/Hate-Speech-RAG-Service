# BYOK 저장 보안과 인젝션 감사

## 범위

2026-07-17 기준 Google 계정, 계정별 Anthropic/Upstage API 키, job별 복호화 경계와 API 입력 및 RAG prompt injection 경로를 점검했다. 키 원문과 암호문은 로그·문서에 출력하지 않았다.

## 확인된 저장 경계

- Google `sub`를 외부 계정 식별자로 사용하고 사용자는 내부 UUID로 참조한다.
- `user_api_keys`는 `(user_id, provider)` unique constraint로 사용자별 공급자 키를 한 건만 유지한다.
- API 키는 provider에서 유효성을 확인한 뒤 Fernet 인증 암호문으로 저장한다.
- 응답은 provider, 마지막 4자리 fingerprint, 유효 상태와 검증 시각만 포함한다.
- 세션 원문은 DB에 저장하지 않고 SHA-256 hash만 저장한다.
- worker는 job의 `user_id`로 해당 사용자 키만 복호화하고 job runtime에 주입한다.
- 실제 개발 PostgreSQL에서 Anthropic/Upstage 2개 row의 복호화 성공, 평문·암호문 불일치와 fingerprint 일치를 값 노출 없이 확인했다.

## API·SQL 인젝션 판단

API 키 입력은 Pydantic 길이 제한, 세션 인증, CSRF 검증과 provider allowlist를 거친다. DB 조회는 SQLAlchemy expression과 bound parameter를 사용하며 키 문자열을 SQL, shell 또는 URL에 결합하지 않는다. 따라서 API 키 입력란을 통한 일반적인 SQL injection과 command injection 경로는 확인되지 않았다.

provider 검증 endpoint는 사용자 입력이 아니라 코드·운영 설정으로 고정된다. 키 원문은 HTTPS 인증 header로만 공급자에 전달되며 LLM prompt에는 포함되지 않는다.

남은 API 위험:

- 키 검증 PUT에 사용자/IP별 rate limit이 없어 인증 사용자가 공급자 검증 호출을 과도하게 만들 수 있다.
- 운영자가 Upstage base URL을 임의 endpoint로 바꾸면 키가 그 endpoint에 전송되므로 production 설정 변경 권한을 제한해야 한다.

## RAG prompt injection 판단

현재 방어:

- 댓글·자막 입력을 JSON 문자열로 직렬화한다.
- 입력과 검색 context를 신뢰하지 않는 데이터로 선언한다.
- 별도 system prompt, 허용 taxonomy와 JSON 결과 계약을 사용한다.
- 카테고리 조합, boolean, 한국어 reasoning과 필수 필드를 검증하고 실패 시 한 번 교정한다.
- LLM에는 tool, DB 또는 shell 실행 권한이 없다.

남은 무결성 위험:

- 유효한 JSON 안에서 원문과 다른 `input_text`나 공격자가 원하는 분류를 반환할 수 있다.
- `similar_cases_used`, `definition_docs_used`가 실제 검색 결과에 포함된 ID인지 검증하지 않는다.
- definition context의 자유 텍스트가 instruction처럼 해석될 수 있다.
- reasoning과 target 문자열의 의미·길이에 대한 결정적 제한이 부족하다.

따라서 현재 prompt injection의 주 영향은 서버 실행권 획득이나 API 키 탈취가 아니라 분류·근거·설명 무결성 훼손이다. 입력에서 `ignore previous instructions` 같은 문구를 삭제하면 연구 원문이 훼손되므로 필터링 대신 system-level 격리와 결과 대조를 강화한다.

개선 우선순위:

1. 불변 규칙과 untrusted-data 규칙을 system prompt로 이동한다.
2. 모델의 `input_text`를 저장하지 않고 source DB 원문을 사용한다.
3. 근거 ID가 실제 retrieval 결과의 부분집합인지 검증한다.
4. reasoning·target_group·hate_type에 길이와 타입 제한을 적용한다.
5. 지원 모델의 structured output/JSON schema를 사용한다.
6. adversarial prompt injection 회귀 corpus를 추가한다.

## secret과 관측 설정

점검 당시 `.env` 권한은 `664`였다. 같은 호스트의 다른 사용자가 Fernet master key와 OAuth secret을 읽을 수 있으므로 배포 전 `600`으로 제한해야 한다. production에서는 `.env` 대신 Secret Manager/KMS 또는 Docker Secret을 사용하고 Fernet 키 버전·재암호화 절차를 마련한다.

Langfuse와 input/output capture는 모두 비활성 상태였다. 향후 capture를 활성화하면 API 키가 아니라 댓글·자막과 전체 prompt가 외부 관측 저장소로 전송될 수 있으므로 별도 보유 기간, 접근 통제와 비식별화가 필요하다.

## 판정

- 계정별 키 연결과 DB 암호화: 적절, 실제 동작 확인
- SQL/command injection: 현재 경로에서 낮음
- secret 운영 관리: `.env` 권한과 master-key 관리 보완 필요
- prompt injection: 기본 방어 존재, semantic integrity 검증 보완 필요
