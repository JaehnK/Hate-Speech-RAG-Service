# BYOK 병렬 처리와 live 댓글 실패 진단

## 진단 대상

- 점검일: 2026-07-17 KST
- job: `c3d7b664-ee4a-4a54-9eae-8ef10adf9f04`
- 소유 계정: Google OAuth 사용자와 `analysis_jobs.user_id` 연결 확인
- 설정: item 2, Upstage 2, Anthropic 2, provider 최대 시도 3

## live 관측 결과

18:04 KST snapshot에서 댓글 703건 중 190건이 완료됐고 172건 성공, 18건 실패였다. 실패 row는 모두 `LLM_ERROR`와 `LLM classification request failed`로 저장됐다.

실패 댓글 평균 길이는 41자, 성공 댓글 평균 길이는 45자였고 성공 댓글의 최대 길이가 더 길었다. 따라서 긴 댓글이나 request size가 주원인이라는 근거는 없다. 처음 약 3분은 실패 없이 처리된 뒤 18:00 KST부터 실패가 발생했고, 같은 구간에서 Anthropic SDK의 `/v1/messages` 자동 재시도 로그가 반복됐다.

Anthropic 공식 문서에 따르면 SDK는 connection error, 429와 5xx를 기본 두 번 자동 재시도한다. 현재 구현은 SDK 내부 재시도 뒤의 최종 예외를 generic `ClassificationError`로 바꿨기 때문에 429, 529, timeout과 connection error 중 어떤 항목이었는지 과거 row에서 복원할 수 없다.

판정:

- 직접 원인: Anthropic message 호출의 provider/transport 오류
- 가장 가능성 높은 범주: rate/acceleration limit 또는 일시적 5xx/connection 오류
- 확정 불가 사유: 기존 error mapping이 원래 exception type과 status를 버림
- 제외 가능성이 높은 항목: 댓글 길이, Upstage retrieval, API 키 401/403

기존 worker로 완료된 최종 결과:

- job status: `succeeded`
- 댓글: 703/703 완료, 682 성공, 21 실패
- 자막 문장: 107/107 성공, 실패 0
- 댓글 network/report/finalize: 모두 성공

댓글 실패율은 약 3.0%이며 기존 generic `LLM_ERROR`로 남았다. item 실패를 허용하는 partial-item 정책에 따라 전체 job과 보고서 생성은 정상 완료됐다.

공식 자료:

- Claude rate limits: https://platform.claude.com/docs/en/api/rate-limits
- Claude API errors: https://platform.claude.com/docs/en/api/errors

## BYOK 이후 동시성 결정

BYOK는 여러 사용자가 서로 다른 provider quota를 사용하게 하므로 사용자 간 병렬 처리 여지는 커진다. 그러나 한 job의 모든 요청은 한 사용자의 Anthropic 조직 한도를 공유하므로 BYOK 자체가 단일 키의 RPM/ITPM/OTPM을 높이지 않는다.

조정값:

| 설정 | 이전 | 조정 | 근거 |
| --- | ---: | ---: | --- |
| item concurrency | 2 | 4 | retrieval과 LLM 대기 overlap 확대 |
| Upstage concurrency | 2 | 4 | live progress에서 embedding retry 0 |
| Anthropic concurrency | 2 | 2 | transient 오류가 이미 관측되어 raw 확대 보류 |

item slot 4개가 retrieval을 진행하더라도 Anthropic semaphore가 최대 2개만 통과시키므로 LLM burst는 확대하지 않는다.

## 오류 가시성 개선

- Anthropic SDK `max_retries=0`으로 숨은 재시도를 끈다.
- 애플리케이션 `RetryPolicy`만 최대 3회 사용해 `Retry-After`, 지수 backoff와 retry metric을 일치시킨다.
- item 결과에 다음 안정적 코드를 저장한다.
  - `LLM_RATE_LIMITED`
  - `LLM_TIMEOUT`
  - `LLM_CONNECTION_ERROR`
  - `LLM_BILLING_ERROR`
  - `LLM_OVERLOADED`
  - `LLM_REQUEST_REJECTED`
  - `LLM_PROVIDER_ERROR`
  - `LLM_OUTPUT_INVALID`
  - `RAG_RETRIEVAL_ERROR`

다음 실행부터 실패율과 error code를 기준으로 Anthropic 동시성을 결정한다. 429/529가 0에 가깝고 p95 latency가 안정적인 경우에만 3으로 단계적으로 올린다. 한 번에 4 이상으로 올리지 않는다.

## 현재 job 적용 경계

진행 중 worker는 재시작하지 않았다. 이 job은 시작 당시 item/Upstage/Anthropic 동시성 2와 기존 generic error mapping으로 완료된다. 새 기본값과 error code는 worker를 안전하게 재기동한 뒤 시작하는 다음 job부터 적용한다.

## 검증 결과

- provider/RAG/worker/config 집중 테스트: `22 passed`
- backend 전체 테스트: `110 passed, 1 skipped`
- Ruff, Python compileall, `git diff --check`: 성공
- dev/test/prod Compose config: 성공
