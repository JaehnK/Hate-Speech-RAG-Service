# 배포 산출물·샘플 데이터셋 인벤토리

| 항목 | 값 |
| --- | --- |
| 기준일 | 2026-07-18 KST |
| 목적 | 배포 또는 포트폴리오 공개 전에 함께 준비해야 하는 문서, 공개 샘플, RAG corpus 자료를 한 곳에서 추적한다. |
| 원칙 | raw 외부 데이터와 vector store volume은 Git에 커밋하지 않는다. 공개 화면에는 운영 secret, prompt 원문, collection 내부 이름, migration/가격 이력을 노출하지 않는다. |

## 1. 공개 사용자 표면

아래 항목은 서비스 방문자 또는 포트폴리오 검토자가 직접 보게 되는 산출물이다.

| 항목 | 경로 | 공개 목적 | 상태 |
| --- | --- | --- | --- |
| 분석 메인 | `/` | 로그인 전에도 제품의 핵심 입력 흐름을 보여주고, 로그인·BYOK 완료 후 실제 분석을 시작한다. | 구현 완료 |
| 공개 샘플 목록 | `/samples` | 로그인 전 검토 가능한 운영자 승인 보고서를 보여준다. | 구현 완료 |
| 공개 샘플 보고서 | `/reports/d4484345-b69d-492e-88c5-a4330a3111e2` | 실제 BYOK 계정으로 재분석한 대표 분석 결과를 제공한다. | 공개 지정 완료 |
| RAG 방법론 요약 | `/rag-methodology` | 재현성과 사회과학적 해석 원칙을 보여주되 민감한 운영 세부는 숨긴다. | 공개용 축약 완료 |

공개 샘플 보고서는 운영자가 댓글 원문, 영상 맥락, 작성자 표시, 분석 사유의 공개 적합성을 검토한 뒤 `is_public_sample=true`로 지정한 report만 포함한다. 샘플 공개 여부는 원본 분석 결과를 수정하지 않는 별도 운영 flag다.

## 2. 배포 전 내부 문서 묶음

아래 문서는 Git 저장소에는 포함하되 public web surface에는 직접 노출하지 않는다. 배포·감사·재현성 확인에 필요한 기준 문서다.

| 문서 | 역할 | 배포 전 확인 포인트 |
| --- | --- | --- |
| `docs/00_project_brief.md` | MVP 목적, 사용자, 범위, 성공 기준 | 현재 기능 범위와 public sample 정책이 일치하는지 확인 |
| `docs/02_hld.md` | 고수준 아키텍처와 주요 API 표면 | frontend/backend 분리, OAuth/BYOK, report 흐름 확인 |
| `docs/03_data_model.md` | DB schema 기준 | user/session/api key/report ownership 필드 확인 |
| `docs/05_api_spec.md` | API 계약 | 공개/비공개 report, auth, job endpoint 경계 확인 |
| `docs/06_report_spec.md` | report snapshot과 export 기준 | report 화면·Excel 항목과 API payload 일치 확인 |
| `docs/10_docker_environment.md` | Docker 실행 환경 | production/dev/test compose 차이와 secret 주입 확인 |
| `docs/12_category_taxonomy.md` | 혐오표현 category 기준 | 코드 taxonomy와 문서 category 동기화 확인 |
| `docs/15_predeploy_runbook.md` | 배포 전 실행 절차 | corpus 생성, E2E, secret scan, production hardening 순서 확인 |
| `docs/19_rag_methodology_reproducibility.md` | RAG 내부 재현성 문서 | prompt, retrieval, corpus, embedding, validation 계약 확인 |
| `docs/30_auth_oauth_byok.md` | Google OAuth/BYOK 설계 | 세션, Fernet, 사용자별 API 키 경계 확인 |
| `docs/31_public_surface_hardening.md` | 공개 표면 정리 기준 | Swagger/OpenAPI 비공개, RAG 공개 요약 수준 확인 |
| `docs/36_byok_security_injection_audit.md` | BYOK 보안·prompt injection 감사 | API 키 보관, LLM 입력 경계, residual risk 확인 |
| `docs/39_comment_evidence_multilingual_corpus_audit.md` | 댓글 근거 UI와 corpus 감사 | citation 한계, 한·영 corpus 확장 전제 확인 |

작업 이력 문서는 `docs/14_delivery_worklog.md`를 기준으로 삼고, 기능별 상세 delivery 문서는 해당 기능의 merge 증적으로 유지한다.

## 3. RAG에 실제 적재하는 자료

현재 production 기본 RAG는 내부 taxonomy와 license가 확인된 K-HATERS 기반 자료만 적재 대상으로 삼는다.

| collection 역할 | source | 적재 내용 | 상태 | 공개/배포 정책 |
| --- | --- | --- | --- | --- |
| 정의·taxonomy | 내부 taxonomy generator | 공통 규칙 10건, category card 13건 | 적재 대상 | Git에 코드와 문서로 포함 |
| 정의·dataset guideline | K-HATERS README chunk | dataset 설명·label 문서 chunk 8건 | 적재 대상 | CC-BY 4.0 attribution 필요 |
| 예시 검색 | K-HATERS train split | 댓글 예시 172,157건 | 적재 대상 | raw data와 Chroma volume은 Git 제외 |

Embed 2로 생성한 vector store는 배포 환경에서 named volume 또는 별도 artifact로 주입할 수 있다. 단, 같은 collection 안에 서로 다른 embedding 모델의 vector를 섞지 않고, collection 생성 시점의 embedding provider/model/dimension/corpus version을 배포 기록에 남겨야 한다.

## 4. 보유하지만 기본 적재하지 않는 샘플 데이터셋

아래 자료는 local inventory에 남겨 두되, 라이선스·대표성·품질 검토가 끝나기 전에는 production retrieval corpus에 넣지 않는다.

| dataset | local inventory | 보류 이유 |
| --- | --- | --- |
| UNSMILE | `data/external/manifests/dataset_sources.yaml` | CC-BY-NC-ND 4.0 계열로 public/commercial retrieval corpus에 부적합 |
| K-MHaS | `data/external/datasets/k-mhas` | 명시 license 파일 미확인, category mapping reference로만 사용 |
| KODOLI | `data/external/datasets/kodoli` | CC-BY-SA 4.0 관찰, ShareAlike 영향 검토 전 example 적재 보류 |
| KOLD | `data/external/datasets/kold` | 사용 제한 문구와 명시 license 미확인 |
| BEEP | `data/external/datasets/beep-korean-hate-speech` | CC-BY-SA 4.0 영향과 guideline 사용 범위 검토 필요 |
| AI Hub Text Ethics | 외부 승인 필요 | 계정 승인·약관 동의 전 다운로드 및 적재 불가 |

세부 파일 hash, record count, source revision은 `data/external/manifests/dataset_inventory.yaml`과 `data/external/manifests/dataset_sources.yaml`을 기준으로 한다.

## 5. 배포 전 체크리스트

1. public sample로 지정된 report ID와 `/samples` 목록이 일치한다.
2. 공개 화면에는 secret, raw prompt, 내부 collection 이름, migration 비용 이력이 노출되지 않는다.
3. `docker compose --profile tools run --rm corpus`로 생성한 corpus count가 정의 31건, 예시 172,157건 기준과 일치한다.
4. K-HATERS CC-BY 4.0 attribution 문구가 public methodology 또는 report 주변에 표시된다.
5. raw dataset 파일, `.chroma`, report export, live E2E evidence는 Git에 포함하지 않는다.
6. 새 dataset을 추가할 때는 `dataset_sources.yaml`, `dataset_inventory.yaml`, 이 문서의 3·4번 표를 함께 갱신한다.
