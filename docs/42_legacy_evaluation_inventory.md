# 레거시 평가 자산 인벤토리

| 항목 | 값 |
| --- | --- |
| 기준일 | 2026-07-18 KST |
| 목적 | 레거시 작업공간에 남아 있는 정확도 평가셋·결과를 현재 Hatescope 평가 체계와 연결하기 위한 위치 기록 |
| 원칙 | 원본 대용량/민감 데이터는 Git에 추가하지 않고, 경로·스키마·사용 가능성만 문서화한다. |

## 1. 발견된 평가 후보

| 자산 | 경로 | 크기 | 판단 |
| --- | --- | ---: | --- |
| UNSMILE validation split | `legacy/hateSpeechRAG/data/raw/korean_unsmile_dataset/unsmile_valid_v1.0.tsv` | 455,383 bytes | 공개 라벨셋 기반 gold 후보 |
| UNSMILE train split | `legacy/hateSpeechRAG/data/raw/korean_unsmile_dataset/unsmile_train_v1.0.tsv` | 1,848,905 bytes | RAG example/taxonomy 학습·검색 후보, test 용도 제외 |
| 과거 평가 결과 A | `legacy/hateSpeechRAG/scripts/hate_speech_evaluation_20250918_183926.json` | 147 bytes | legacy RAG의 UNSMILE 평가 지표 |
| 과거 평가 결과 B | `legacy/hateSpeechRAG/data/processed/hate_speech_evaluation_20250831_173922.json` | 148 bytes | legacy RAG의 이전 UNSMILE 평가 지표 |
| 과거 YouTube batch 결과 | `legacy/hateSpeechRAG/data/batch_results/classify_20250912_233832/classify_results_20250912_233832.csv` | 473,463,966 bytes | 모델 산출물, gold label 아님 |
| 과거 YouTube RAG 결과 | `legacy/hateSpeechRAG/data/batch_results/classify_20250912_233832/comment_rag_result_20250912_233832.json` | 486,373,180 bytes | 모델 산출물, gold label 아님 |
| 과거 Chroma vectorstore | `legacy/hateSpeechRAG/data/vectorstores/hate_speech_vectorstore/` | 약 274 MB | 단일 컬렉션 legacy vectorstore, 현재 three-vector 구조와 직접 호환 불가 |

위 `legacy/hateSpeechRAG/` 하위 파일들은 `.gitignore`에 의해 제외되어 있다. 따라서 이 문서는 원본 파일을 커밋하지 않고 현재 로컬 작업공간에서 확인된 위치만 기록한다.

## 2. UNSMILE schema

레거시 validation split은 다음 열을 갖는다.

| 열 | 의미 |
| --- | --- |
| `문장` | 분류 대상 텍스트 |
| `여성/가족` | 여성·가족 관련 혐오 라벨 |
| `남성` | 남성 관련 혐오 라벨 |
| `성소수자` | 성소수자 관련 혐오 라벨 |
| `인종/국적` | 인종·국적 관련 혐오 라벨 |
| `연령` | 연령 관련 혐오 라벨 |
| `지역` | 출신지역 관련 혐오 라벨 |
| `종교` | 종교 관련 혐오 라벨 |
| `기타 혐오` | 기타 혐오 라벨 |
| `악플/욕설` | 욕설·악플 라벨 |
| `clean` | 비혐오 라벨 |
| `개인지칭` | 개인 지칭성 라벨 |

레거시 평가 스크립트는 이 원본 라벨을 서비스용 6축으로 접었다.

| 현재 서비스 축 | 레거시 UNSMILE 매핑 |
| --- | --- |
| `성별` | `여성/가족`, `남성`, `성소수자` 중 하나라도 1 |
| `연령` | `연령` |
| `정체성` | `인종/국적`, `지역`, `종교` 중 하나라도 1 |
| `욕설` | `악플/욕설` |
| `기타` | `기타 혐오`, `개인지칭` 중 하나라도 1 |
| `혐오없음` | `clean` |

이 매핑은 `legacy/hateSpeechRAG/scripts/PerformanceTest.py`의 `test_unsmile_dataset()`에 남아 있다.

## 3. 과거 평가 결과

`legacy/hateSpeechRAG/scripts/hate_speech_evaluation_20250918_183926.json`:

```json
{
  "binary_f1": 0.8574057037718491,
  "hamming_loss": 0.17411869701026328,
  "exact_match": 0.2294511378848728,
  "macro_f1": 0.5570395130939418
}
```

`legacy/hateSpeechRAG/data/processed/hate_speech_evaluation_20250831_173922.json`:

```json
{
  "binary_f1": 0.8554867079752149,
  "hamming_loss": 0.13642041399000715,
  "exact_match": 0.49598501070663814,
  "macro_f1": 0.6365224356040577
}
```

이 수치는 레거시 프롬프트, 레거시 단일 vectorstore, 당시 모델 설정에서 산출된 결과다. 현재 `category-rag-v0.3.1` three-vector RAG의 직접 성능으로 인용하면 안 된다.

## 4. 현재 평가 체계에 반영하는 방법

권장 순서:

1. UNSMILE valid를 현재 evaluator 입력 형식으로 변환한다.
   - 검증: 변환 row 수가 `3,737`개인지 확인한다. TSV header를 제외한 수량이다.
2. 현재 service category로 매핑된 gold JSONL을 생성한다.
   - 검증: `성별/연령/정체성/욕설/기타/혐오없음` 외 라벨이 없어야 한다.
3. `three_vector_rag`, `definitions_only`, `examples_only`, `haiku_only`를 같은 gold set에서 비교한다.
   - 검증: 동일 입력, 동일 gold, 동일 반복 횟수로 coverage·binary F1·category micro F1을 산출한다.
4. 별도로 실제 YouTube 댓글 gold set을 구축한다.
   - 검증: 공개 라벨셋 성능과 실제 YouTube 성능을 분리해 보고한다.

UNSMILE은 모델 회귀와 카테고리 감도 확인에는 유용하지만, 실제 서비스 정확도 주장은 YouTube 댓글·답글·자막에서 익명화한 별도 gold set이 있어야 한다.

## 5. 공개/포트폴리오 표현 가이드

가능:

- “공개 한국어 혐오표현 라벨셋 기반 회귀 평가 자산을 보유하고 있다.”
- “레거시에서는 UNSMILE valid 기준 binary F1 약 0.86 수준의 과거 실험 결과가 있었다.”
- “현재 three-vector RAG와 BYOK 구조에서는 같은 평가셋으로 재측정해야 한다.”

피해야 함:

- “현재 Hatescope의 YouTube 분석 정확도는 0.86이다.”
- “레거시 UNSMILE 결과가 현재 three-vector RAG 성능이다.”
- “공개 라벨셋 하나로 실제 YouTube 댓글 전체 성능을 대표한다.”
