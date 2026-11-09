# 후속 작업 백로그

| 항목 | 값 |
| --- | --- |
| 작성일 | 2026-11-09 KST |
| 범위 | 모델 비교(test셋)와 운영 반영 이후에 진행할 작업 |

현재 진행 순서는 ① taxonomy v0.5.1 dev 확인 → ② test셋 970건에서 Jev+Haiku·Haiku·Sonnet·Opus 비교 → ③ 운영 반영(모델·taxonomy·규범 corpus) → ④ 문서 정리다. 아래 항목은 그 이후 단계다.

## 1. Upstage 임베딩을 서버 키로 전환 (2026-11-09 코드 반영)

사용자는 Anthropic 키만 등록하고, 임베딩은 운영자 키로 처리한다.

- 근거: 임베딩 비용은 댓글 1,000개당 1센트 미만이다. 검색 corpus가 서버 임베딩 모델로 만들어져 있어 질의 임베딩도 서버가 통제하는 편이 맞다. 사용자별 기본 등급 키에서 나던 429 실패가 사라지고, 운영자가 등급을 올려 전체 처리량을 늘릴 수 있다.
- 작업:
  - [x] 서버 공용 `UPSTAGE_API_KEY` 사용, 분석 요청 시 Anthropic 키만 필수로 변경
  - [x] 설정 화면과 안내 문구에서 Upstage 키 등록 제거 (기존 저장 키는 무시, 삭제만 허용)
  - 사용자별 일일 분석 횟수 제한
  - 월 사용량 모니터링·상한
  - 개인정보 처리방침에 Upstage·TypeSafe 전송 반영
  - Upstage 콘솔에서 등급별 한도 확인 후 등급 결정

## 2. 처리량·비용 최적화

건당 처리 시간은 중앙값 7초(LLM 약 5초)이고, 프롬프트 v0.6.x 입력은 건당 약 8,700토큰이다.

외부 한도는 병목이 아니다. Anthropic Start 등급(RPM 4,000, ITPM 2M, OTPM 400K)이면 사용자 키 하나로 분당 약 230건(ITPM 기준)까지 처리할 수 있고, 이를 채우려면 동시 처리 약 27개가 필요하다. 현재 worker 설정은 최대 16(기본 4)이라 분당 약 137건에서 먼저 막힌다. 실제 병목은 worker 동시 처리 설정과 운영 VM(e2-micro)의 벡터 검색 CPU다. Upstage는 Solar Pro 3 기준 초당 30회로 안내되지만, 실험에서 임베딩은 분당 약 230회에서 429가 났으므로 임베딩 모델의 한도를 콘솔에서 따로 확인한다.

| 작업 | 기대 효과 | 비고 |
| --- | --- | --- |
| 고정 프롬프트 부분(지시문, 고정 규칙 카드) 프롬프트 캐싱 | 입력 비용·사용자 토큰 한도 사용량 감소 | 규범 문서·사례는 댓글마다 달라 캐싱 대상 아님 |
| 규범 문서 슬롯 축소(7 → 5) | 입력 토큰 약 20~30% 감소 예상 | dev셋에서 정확도·인용률 유지 확인 필요 |
| 429 기반 동시 처리 자동 조절 | 사용자 Anthropic 등급에 맞춰 처리량 자동 최적화 | 현재 `RAG_ITEM_CONCURRENCY` 고정값 |
| 댓글 임베딩 공유 캐시 | 같은 영상 재분석·다중 사용자 분석 시 임베딩 재사용 | Upstage 서버 키 전환 후 |
| VM 검색 CPU 측정 | 동시 처리 상한 근거 확보, 필요 시 VM 상향 | 운영 worker는 e2-micro |
| 실험 스크립트: 임베딩 디스크 캐시 + 동시 처리 20 | dev·test 평가 20분 → 약 6분 | 실험 전용, test 비교 전에 적용 가능 |

### 운영 VM 동시 처리 설정 (2026-11-09 확인)

운영 worker는 기본값 그대로 `RAG_EXECUTION_MODE=sequential`, `RAG_LLM_CONCURRENCY=2`로 돌고 있어 분당 약 8건만 처리한다. VM은 메모리 969MB(가용 359MB)에 swap이 없다.

1. swap 2GB 추가(OOM 강제 종료 방지)
2. `parallel`, `RAG_ITEM_CONCURRENCY=4`, `RAG_LLM_CONCURRENCY=4`로 변경 후 worker 재시작
3. 실제 분석 1회 동안 최대 메모리 측정, 여유가 있으면 8로 상향

## 3. 실제 YouTube 댓글 정답셋 구축

실제 YouTube 댓글에 사람이 혐오표현 라벨을 붙인 정답셋은 아직 없다. 현재 정확도는 공개 benchmark(K-HATERS·BEEP) 기준이다.

- 기존 자료의 한계:
  - legacy 인터코더 결과셋(2,377건)은 실제 댓글을 사람이 코딩했지만 분류 축이 허위·오정보다.
  - legacy 댓글 결과(21,987건)는 이전 RAG 파이프라인의 판정이라 정답이 아니다.
- 계획:
  - 실제 댓글 300~500건을 영상별로 고르게, 혐오가 섞이도록 층화 추출한다.
  - taxonomy v0.5.1 기준 코드북으로 라벨링한다.
  - `docs/43`의 반자동 방식(모델 간 판정이 갈린 댓글 우선 검토)으로 작업량을 줄인다.
  - 가능하면 라벨러 2명으로 일치도(Cohen's kappa)를 보고한다.
- 결과: "실제 YouTube 댓글 기준 정확도"와 Jev 필터의 실제 누락률을 측정할 수 있다.

## 4. 인프라 자동화 (IaC·CI/CD)

현재는 `gcloud`로 수동 배포하고, CI(`ci.yml`)는 테스트만 실행한다.

- Terraform:
  - GCS 버킷에 state 저장(잠금 포함)
  - 운영 중인 리소스를 `terraform import`로 편입: Cloud Run 2개, VM, 방화벽, Artifact Registry, Secret Manager secret, 도메인 매핑
  - 모듈: network, compute, run, registry, secrets(secret 값은 코드에 넣지 않음)
  - PR마다 `terraform plan`, main에서만 `apply`
- GitHub Actions 배포:
  - Workload Identity Federation으로 서비스 계정 키 파일 없이 인증
  - main 병합 시: 이미지 빌드(git SHA 태그) → Artifact Registry 푸시 → Alembic 마이그레이션 → Cloud Run 새 revision → VM worker 갱신(IAP) → `/health` 확인, 실패 시 이전 revision으로 롤백
  - 운영 배포 전 GitHub Environment 수동 승인
- 검토: worker를 Cloud Run Jobs·서비스로 옮겨 VM에는 DB만 남기는 구조

## 5. 보류한 기능 아이디어

범위를 고정하기로 해서 당분간 진행하지 않는다.

- 심각도 단계 판정(불법·선동 / 집단 혐오 / 공격적 표현)과 보고서 단계별 집계
- 해외 기준 원문 적재 확대(현재는 요약 카드)
- 규범 문서 검색 추가 개선(현재 category 일치율 54.9%)
- taxonomy 기반 Jev 질문(v2) 실험

