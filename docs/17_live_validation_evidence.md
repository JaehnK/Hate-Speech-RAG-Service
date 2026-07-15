# 실제 외부 API 검증 증적

| 항목 | 값 |
| --- | --- |
| 최종 검증일 | 2026-07-15 |
| 브랜치 | `chore/live-e2e-validation`, `docs/production-comment-validation` |
| 실행 모드 | `APP_ENV=production`, `PIPELINE_MODE=production` |
| 런타임 | PostgreSQL 16 + migration + web + worker Docker Compose |
| 외부 서비스 | YouTube Data API v3, 공개 자막 adapter, Anthropic, Upstage |
| 비밀값 | 일회성 admin/DB secret 사용, 원문 미기록 |

## 1. Corpus와 retrieval

라이선스가 확인된 K-HATERS를 production example 대상에 포함하고, 외부 API 비용을 제한한 smoke corpus를 named volume과 별도 임시 store에 각각 생성했다.

- internal definition: 18건
- 허용된 external definition: 8건
- K-HATERS example: 100건 제한 적재
- Upstage `solar-embedding-1-large` 실제 호출 성공
- definition/example 양쪽 collection 실제 검색 성공
- 256건 요청의 실제 `400`을 확인해 batch 상한을 100으로 교정
- 513건을 `100/100/100/100/100/13`으로 실제 Upstage 적재 성공하고 동일 회귀 테스트 추가

100건 제한은 외부 연결과 실행 경로를 증명하기 위한 smoke 조건이다. 배포 대상 전체 corpus는 `docker compose --profile tools run --rm corpus`로 limit 없이 다시 생성해야 한다.

## 2. RAG 개선 검증

초기 실제 4-variant × 5개 합성 입력 × 3회 반복에서 60/60 API 호출은 성공했지만, `dual_rag`가 `definitions_only`보다 낮았다.

| 단계 | variant | binary accuracy | category micro F1 | repeat stability | 판정 |
| --- | --- | ---: | ---: | ---: | --- |
| v0.1 진단 | `definitions_only` | 1.000 | 1.000 | 1.000 | 기준선 |
| v0.1 진단 | `dual_rag` | 0.867 | 0.500 | 0.800 | 회귀 발견 |
| v0.2 본문/라벨 전달 | `dual_rag` | 0.800 | 0.000 | 1.000 | 무관 예시 영향 확인 |
| v0.2 + similarity 0.40 | `dual_rag` | 1.000 | 1.000 | 1.000 | 15/15 성공, retry 0 |

원인은 검색 예시 본문과 `is_hate_speech` 라벨이 prompt에서 누락됐고, 제한 corpus의 낮은 유사도 예시가 정의 근거를 덮은 것이었다. 다음을 반영했다.

- prompt를 `category-rag-v0.2.0`으로 올리고 example 본문·라벨을 JSON data로 전달
- 입력과 retrieval context를 신뢰하지 않는 data로 명시해 내부 지시 실행 방지
- `example_min_similarity=0.40` 미만 예시는 prompt와 사용 후보에서 제외
- prompt version과 retriever config를 analysis run 및 report snapshot에 기록

위 수치는 합성 smoke 5건의 실행 회귀 지표이며 운영 품질 수치가 아니다. 배포 승인에는 익명화한 실제 댓글·스크립트의 2인 독립 라벨 gold set이 필요하다.

## 3. Production live E2E

최종 이미지에서 `scripts.live_e2e`가 report의 prompt version과 retriever threshold까지 확인했다.

| 시나리오 | 영상 ID | job | 댓글 | script segment | HTML bytes | XLSX bytes |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 정상 | `WCoWEUBviJ0` | `succeeded` | 1 | 2 | 1,988 | 9,184 |
| 댓글 비활성 | `oVTbpKoSTQk` | `partial_success` | 0 | 1 | 2,337 | 8,483 |
| 공개 자막 없음 | `yP44l94hFOQ` | `partial_success` | 2 | 0 | 2,114 | 8,919 |

추가 확인:

- 정상 job의 10개 step 모두 `succeeded`
- 댓글 비활성은 `collect_comments`와 `analyze_comments`가 계약대로 `skipped`
- 자막 없음은 `collect_transcript`와 `analyze_script`가 계약대로 `skipped`
- snapshot 수와 분석 결과 수 일치
- report/comments/script/network API 응답 성공
- HTML/XLSX 6개 export 생성·다운로드 성공 및 비어 있지 않음
- 관리자 settings/jobs/logs/quota surface 성공
- YouTube/Anthropic/Upstage key configured 상태 확인
- 캡처한 JSON API 응답의 admin/YouTube/Anthropic/Upstage secret 원문 검색 통과
- raw 댓글·자막은 증적 JSON에 포함하지 않음

기계 판독 원본은 Git에서 제외된 `experiments/outputs/live_e2e_evidence.json`에 보관한다.

## 4. 프론트 경유 production 댓글 수집 재검증

Stitch 기반 프론트가 추가된 뒤 `http://localhost:3000/api` reverse proxy를 통해 새 production job을 생성하고 완료까지 확인했다.

| 항목 | 결과 |
| --- | --- |
| 영상 ID | `uzpQb_wZdzk` |
| job ID | `cc9d5bdf-086f-41ed-b0dd-1fc3a6b61315` |
| report ID | `102ef561-a63f-431d-8a81-a3957e7b0d3e` |
| 최종 상태 | `succeeded`, progress 100% |
| 댓글 | 수집 11, 분석 성공 11, 실패 0 |
| script segment | 수집 37, 분석 성공 37, 실패 0 |
| 네트워크 | node 11, edge 0 |
| export | HTML 2,247 bytes, XLSX 28,748 bytes |

추가 확인:

- 댓글 상세 API가 11개 항목을 반환했다.
- 프론트 report SPA 경로가 HTTP 200을 반환했다.
- `PIPELINE_MODE=fake`에서는 외부 수집 없이 0건으로 성공 처리됨을 확인하고 로컬 실행 설정을 `production`으로 교정했다.
- `httpx`와 `httpcore` INFO 로그를 제한한 뒤 worker 로그의 YouTube API key 패턴 검색 결과가 0건이었다.

## 5. 남은 배포 승인 조건

구현 및 외부 API 실행 경로는 배포 직전 상태로 검증됐다. 실제 배포 버튼을 누르기 전 운영 환경에서 다음을 별도로 승인한다.

1. limit 없는 전체 K-HATERS corpus 적재와 count/retrieval 확인
2. 실제 익명화 gold set의 2인 독립 라벨링·불일치 조정
3. 네 variant의 실제 gold 평가에서 dual RAG 비열화 확인
4. 운영 secret manager, TLS ingress, backup/restore, quota/비용 한도 확인
