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
| 실제 댓글 인터코더 결과셋 | `legacy/YouTubeHateSpeech/ergm/Comment_.xlsx` | 400,004 bytes | 실제 YouTube 댓글 기반 수작업 코딩 결과셋 |
| 실제 댓글 분석 결과 workbook | `legacy/hateSpeechRAG/scripts/youtube_comments_20250909_111405.xlsx` | 5,844,122 bytes | 실제 YouTube 댓글에 legacy RAG 분석 결과가 붙은 산출물 |
| 실제 자막 분석 결과 workbook | `legacy/hateSpeechRAG/scripts/scripts.xlsx` | 5,725,754 bytes | 실제 영상 자막/스크립트 세그먼트에 legacy RAG 분석 결과가 붙은 산출물 |
| 과거 평가 결과 A | `legacy/hateSpeechRAG/scripts/hate_speech_evaluation_20250918_183926.json` | 147 bytes | legacy RAG의 UNSMILE 평가 지표 |
| 과거 평가 결과 B | `legacy/hateSpeechRAG/data/processed/hate_speech_evaluation_20250831_173922.json` | 148 bytes | legacy RAG의 이전 UNSMILE 평가 지표 |
| 과거 YouTube batch 결과 | `legacy/hateSpeechRAG/data/batch_results/classify_20250912_233832/classify_results_20250912_233832.csv` | 473,463,966 bytes | 모델 산출물, gold label 아님 |
| 과거 YouTube RAG 결과 | `legacy/hateSpeechRAG/data/batch_results/classify_20250912_233832/comment_rag_result_20250912_233832.json` | 486,373,180 bytes | 모델 산출물, gold label 아님 |
| 과거 Chroma vectorstore | `legacy/hateSpeechRAG/data/vectorstores/hate_speech_vectorstore/` | 약 274 MB | 단일 컬렉션 legacy vectorstore, 현재 three-vector 구조와 직접 호환 불가 |

위 `legacy/hateSpeechRAG/` 하위 파일들은 `.gitignore`에 의해 제외되어 있다. 따라서 이 문서는 원본 파일을 커밋하지 않고 현재 로컬 작업공간에서 확인된 위치만 기록한다.

## 2. 실제 댓글 인터코더 결과셋

`legacy/YouTubeHateSpeech/ergm/Comment_.xlsx`의 `for_Intercoder` 시트는 실제 YouTube 댓글을 대상으로 한 수작업 코딩 결과셋으로 보인다. 총 `2,377`개 row가 있으며, 첫 row에는 코드북 성격의 설명값이 섞여 있다.

| 열 | 확인된 의미 |
| --- | --- |
| `영상id` | YouTube video id |
| `id` | 댓글 row id |
| `comment_text` | 실제 댓글 원문 |
| `F1` | 팩트체킹 여부 |
| `F2` | 실제거짓 여부 |
| `F3` | 허위성 |
| `I1` | A그룹 |
| `I2` | B그룹 |
| `I3` | C그룹 |
| `I4` | 의도성 |
| `FC` | 최종분류 |
| `Note` | 코더 비고 |

`FC` 최종분류 분포:

| 최종분류 | 건수 |
| --- | ---: |
| 오정보 | 1,045 |
| 일반 댓글 | 747 |
| 허위조작정보 | 563 |
| 악의적 정보 | 21 |
| 최종분류 | 1 |

이 파일은 “실제 댓글 기반 결과셋”이라는 점에서 중요하지만, 현재 Hatescope의 혐오표현 카테고리 gold set과는 목적이 다르다. 현 분류축은 허위·오정보·의도성 중심이고, 현재 서비스 축은 혐오표현 여부, 혐오 카테고리, 대상 집단, 혐오 유형이다. 따라서 이 파일을 곧바로 혐오표현 정확도 평가 gold로 쓰면 안 된다.

다만 다음 용도로는 가치가 크다.

1. 실제 YouTube 댓글 분포를 반영한 smoke/regression 입력셋
   - 검증: `comment_text`를 익명화하고 현재 evaluator input JSONL로 변환한다.
2. 별도 “정치 허위정보/오정보 분석” 확장 모듈의 gold 후보
   - 검증: `FC`를 목표 라벨로 두고 현재 혐오표현 prompt와 분리된 classifier를 설계한다.
3. 혐오표현 gold 구축을 위한 샘플링 프레임
   - 검증: 이 댓글 중 일부를 별도 2인 라벨링으로 재코딩해 혐오표현 gold를 새로 만든다.

현재 문서에서 말하는 “실제 YouTube gold set 부재”는 “현재 혐오표현 분류축에 맞춘 gold set이 없다”는 뜻으로 정정한다. 실제 댓글 기반의 수작업 결과셋 자체는 레거시에 존재한다.

## 3. 실제 분석 결과 workbook

레거시에는 실제 YouTube 댓글·자막에 legacy RAG 산출값을 붙인 workbook도 있다.

| 자산 | workbook row 수 | 변환 가능 row 수 | 주요 필드 | 판단 |
| --- | ---: | ---: | --- | --- |
| `legacy/hateSpeechRAG/scripts/youtube_comments_20250909_111405.xlsx` | 21,989 | 21,987 | `comment_text`, `is_hate_speech`, `categories`, `target_group`, `hate_type`, `used_prompt` | 실제 댓글 분석 결과셋 |
| `legacy/hateSpeechRAG/scripts/scripts.xlsx` | 11,891 | 11,891 | `video_id`, `script_index`, `input_text`, `is_hate_speech`, `categories`, `reasoning` | 실제 자막/스크립트 분석 결과셋 |

댓글 workbook의 legacy RAG 분포:

| 값 | 건수 |
| --- | ---: |
| `is_hate_speech=False` | 19,265 |
| `is_hate_speech=True` | 2,722 |

자막 workbook의 legacy RAG 분포:

| 값 | 건수 |
| --- | ---: |
| `is_hate_speech=False` | 10,912 |
| `is_hate_speech=True` | 979 |

이 두 파일은 실제 운영형 데이터 분포를 보는 데 중요하다. 하지만 `is_hate_speech`와 `categories`는 사람이 확정한 gold label이 아니라 legacy RAG 산출값으로 보인다. 따라서 “과거 실제 분석 결과셋”으로는 쓸 수 있지만, 정확도 평가의 정답지로 쓰려면 별도 검수·재라벨링이 필요하다.

댓글 workbook은 원 row 중 `comment_text`가 빈 2건을 변환에서 제외한다. 인터코더 workbook은 코드북 row 1건과 빈 row 1건을 제외해 2,375건이 변환 가능하다.

권장 용도:

1. 현재 Hatescope 샘플 페이지/보고서 데모용 후보
   - 검증: 민감 원문, 작성자명, channel id를 제거한 익명화 샘플만 사용한다.
2. 현재 three-vector RAG 재분석 비교 입력셋
   - 검증: legacy 산출값과 current 산출값을 나란히 비교하되, 일치율을 정확도로 부르지 않는다.
3. 혐오표현 gold 구축용 샘플링 풀
   - 검증: 모델 산출값을 참고값으로만 두고, gold label은 별도 코더가 확정한다.

반자동 gold 후보 구축 명령과 review queue 생성 절차는 `docs/43_semi_automatic_gold_pipeline.md`를 기준으로 한다.

## 4. UNSMILE schema

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

## 5. 과거 평가 결과

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

## 6. 현재 평가 체계에 반영하는 방법

권장 순서:

1. UNSMILE valid를 현재 evaluator 입력 형식으로 변환한다.
   - 검증: 변환 row 수가 `3,737`개인지 확인한다. TSV header를 제외한 수량이다.
2. 현재 service category로 매핑된 gold JSONL을 생성한다.
   - 검증: `성별/연령/정체성/욕설/기타/혐오없음` 외 라벨이 없어야 한다.
3. `three_vector_rag`, `definitions_only`, `examples_only`, `haiku_only`를 같은 gold set에서 비교한다.
   - 검증: 동일 입력, 동일 gold, 동일 반복 횟수로 coverage·binary F1·category micro F1을 산출한다.
4. `Comment_.xlsx`, `youtube_comments_20250909_111405.xlsx`, `scripts.xlsx`에서 실제 댓글·자막 샘플을 뽑아 혐오표현 gold set을 구축한다.
   - 검증: 기존 `FC` 라벨은 보존하되, 혐오표현 라벨은 별도 필드로 2인 이상 재코딩한다.

UNSMILE은 모델 회귀와 카테고리 감도 확인에는 유용하지만, 실제 서비스 정확도 주장은 YouTube 댓글·답글·자막에서 익명화한 별도 gold set이 있어야 한다.

## 7. 공개/포트폴리오 표현 가이드

가능:

- “공개 한국어 혐오표현 라벨셋 기반 회귀 평가 자산을 보유하고 있다.”
- “실제 YouTube 댓글 기반 인터코더 결과셋을 보유하고 있으나, 현재 혐오표현 축으로는 재라벨링이 필요하다.”
- “실제 댓글·자막에 대한 legacy RAG 분석 결과셋을 보유하고 있으며, 현재 모델과 비교 재분석할 수 있다.”
- “레거시에서는 UNSMILE valid 기준 binary F1 약 0.86 수준의 과거 실험 결과가 있었다.”
- “현재 three-vector RAG와 BYOK 구조에서는 같은 평가셋으로 재측정해야 한다.”

피해야 함:

- “현재 Hatescope의 YouTube 분석 정확도는 0.86이다.”
- “레거시 UNSMILE 결과가 현재 three-vector RAG 성능이다.”
- “`Comment_.xlsx`의 `FC` 라벨이 현재 혐오표현 gold label이다.”
- “legacy RAG 산출값과 현재 RAG 산출값의 일치율이 정확도다.”
- “공개 라벨셋 하나로 실제 YouTube 댓글 전체 성능을 대표한다.”
