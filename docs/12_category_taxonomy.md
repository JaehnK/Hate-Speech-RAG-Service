# 혐오 카테고리 분류 체계

| 항목 | 값 |
| --- | --- |
| 버전 | v0.3.0 |
| 작성일시 | 2026-07-16 KST |

## 문서 목적

이 문서는 단일 YouTube 영상 혐오표현 분석 MVP에서 사용할 혐오 카테고리 분류 체계를 정의한다.

MVP의 핵심 분석 단위는 단순한 혐오표현 여부가 아니라, 어떤 기준으로 어떤 혐오 카테고리에 분류되었는지다.

## 핵심 원칙

- 혐오 여부는 주요 결과이지만 최종 목적이 아니다.
- 보고서의 핵심 지표는 카테고리 분포, 카테고리별 대표 사례, 카테고리별 네트워크 분포다.
- `is_hate_speech`는 카테고리 판단을 요약하는 보조 필드로 본다.
- 카테고리는 사람이 검토하고 논쟁할 수 있는 명시적 기준을 가져야 한다.
- RAG 예시 검색과 정의 문서 검색은 카테고리 판단 근거를 보강하기 위한 자료다.

## 평가 데이터의 범위

현재 `hateSpeechRAG`의 프롬프트는 단순 이진 분류가 아니라 다음 필드를 생성한다.

- `is_hate_speech`
- `categories`
- `target_group`
- `hate_type`
- `reasoning`
- `similar_cases_used`

따라서 평가도 이진 F1만으로는 충분하지 않다.

기존 UNSMILE 데이터셋은 `성별`, `연령`, `정체성`, `욕설`, `기타`, `혐오없음` 계열의 기본 혐오표현 평가에는 사용할 수 있다.

하지만 현재 프롬프트가 사용하는 정치 혐오 카테고리 6종은 UNSMILE 정답셋만으로 검증할 수 없다.

## MVP 카테고리 목록

MVP의 `categories` 필드는 다음 카테고리만 허용한다.

| 코드 | 이름 | 설명 | 복수 선택 |
| --- | --- | --- | --- |
| `gender` | 성별 | 성별, 성역할, 가족 역할을 근거로 한 모욕, 비하, 차별 표현 | 가능 |
| `age` | 연령 | 특정 연령대 또는 세대를 근거로 한 모욕, 비하, 차별 표현 | 가능 |
| `identity` | 정체성 | 출신지역, 인종, 국적, 종교, 성적지향, 장애 등 보호 속성 기반 표현 | 가능 |
| `profanity` | 욕설 | 직접적인 욕설, 비속어, 모욕적 호칭이 포함된 표현 | 가능 |
| `state_authority` | 국가 권위체 | 국가 기관, 공직자, 공적 권위체를 표적으로 하는 정치 혐오 표현 | 가능 |
| `non_state_authority` | 비국가 권위체 | 정당, 정치인, 언론, 기업 등 비국가 권위체를 표적으로 하는 정치 혐오 표현 | 가능 |
| `state_regime` | 국가 제도 | 선거 제도, 법, 정책, 행정 절차 등 국가 시스템을 표적으로 하는 정치 혐오 표현 | 가능 |
| `non_state_regime` | 비국가 제도 | 정당 경선, 내부 규칙, 비국가 조직의 제도나 절차를 표적으로 하는 정치 혐오 표현 | 가능 |
| `state_community` | 국가 공동체 | 국민, 시민, 유권자라는 정치적 구성원 지위를 표적으로 하는 정치 혐오 표현 | 가능 |
| `non_state_community` | 비국가 공동체 | 정치 지지층, 팬덤, 이념 집단, 온라인 정치 커뮤니티를 표적으로 하는 정치 혐오 표현 | 가능 |
| `no_target` | 대상 없음 | 혐오적 표현은 있으나 명시적 대상이 식별되지 않는 경우 | 가능 |
| `other` | 기타 | 혐오표현으로 판단되지만 위 카테고리에 넣을 수 없는 경우 | 불가 |
| `unclassified` | 비혐오·미분류 | 혐오표현이 아니거나 문맥상 공격으로 확정할 수 없는 경우 | 불가 |

## 공통 판정 문턱과 문맥 예외

category를 고르기 전에 다음 두 단계를 먼저 적용한다.

1. 공격 대상의 정체성, 소속, 지위 등을 근거로 한 **열등성·무가치 일반화, 비인간화, 배제·차별, 위협·폭력, 제거·억압 선동, 심각한 직접 모욕** 중 하나 이상이 있는지 확인한다.
2. 불쾌함, 반대, 풍자, 사실 서술, 정책·행위 비판만 있는 경우는 `unclassified`로 판정한다. 명확하지 않은 사례를 억지로 혐오 category에 넣지 않는다.

뉴스 보도, 연구·교육, 반박·비판 목적으로 혐오표현을 인용하고 화자가 동조하지 않으면 인용된 단어만으로 혐오로 판정하지 않는다. 풍자·반어는 문자 그대로가 아니라 실제 공격 대상과 화자의 태도를 확인한다. 수집된 item만으로 이를 확정할 수 없으면 `unclassified`를 선택한다.

## Category 판정 카드

### 보호 속성과 표현 방식

| 코드 | 포함 기준 | 제외 기준 | 핵심 경계 |
| --- | --- | --- | --- |
| `gender` | 성별 집단의 열등성 일반화, 성별을 이유로 한 배제·폭력, 성역할 위반에 대한 모욕 | 성별 통계·정책 토론, 성별과 무관한 개인 행동 비판 | 성적지향·트랜스젠더·비이분법 공격은 `identity`; 두 근거가 함께 있으면 복수 선택 |
| `age` | 연령·세대 전체의 무능·해악 일반화, 연령에 따른 권리·참여 배제, 나이에 근거한 모욕 | 연령별 특성 설명, 세대 정책·이해관계 비판, 개인 행동 비판 | 세대의 정치 지지 성향이 표적이면 `non_state_community`도 검토 |
| `identity` | 지역·인종·민족·국적·종교·성소수자·장애 집단 비인간화, 추방·차별·폭력 주장, 집단 멸칭 | 문화·종교·국적 정보, 정치 이념·정당 지지층 공격, 미정의 속성 공격 | 국적·민족 정체성 공격은 `identity`; 시민·유권자 지위 공격은 `state_community` |
| `profanity` | 사람·집단을 직접 부르는 욕설·멸칭, 다른 category 공격을 강화하는 비속어 | 비동조 인용, 대상 없는 감탄·강조, 욕설이 아닌 단순 불쾌 의견 | 공격 방식 category이므로 표적 category와 함께 사용 가능; 표적이 없으면 `no_target` 병기 |

### 정치적 표적 2축

정치 category는 먼저 `state/non_state`, 다음으로 `authority/regime/community`를 판정한다. 정치적 반대나 강한 정책 비판만으로는 부족하며 공통 판정 문턱을 먼저 충족해야 한다.

| 코드 | 표적 | 포함 기준 | 제외·경계 |
| --- | --- | --- | --- |
| `state_authority` | 국가기관·법률상 공직자 | 정부·국회·법원·수사기관·공직자 직무 집단의 비인간화, 위협·제거 선동 | 결정·수사·판결·업무 비판은 제외; 법·정책·절차 자체는 `state_regime` |
| `non_state_authority` | 비국가 조직·지도자 | 정당·후보·정치인·언론·기업·시민단체 지도부의 집단 모욕, 위협·제거 선동 | 공약·보도·사업 결정 비판은 제외; 지지자·일반 구성원은 `non_state_community` |
| `state_regime` | 국가 제도·공식 절차 | 헌정·선거·사법·행정 제도 전체의 악성 일반화, 폭력적 파괴 선동 | 정책 효과·정당성·위헌성 비판과 개정 요구는 제외 |
| `non_state_regime` | 비국가 규칙·절차 | 경선·공천·당규·편집·플랫폼 규칙 전체의 악성 일반화, 파괴 선동 | 절차 오류·불공정성 비판은 제외; 조직·지도자 자체는 `non_state_authority` |
| `state_community` | 국민·시민·유권자 | 국가 구성원 전체의 무가치·위험성 일반화, 권리 박탈·배제·폭력 주장 | 여론·투표 결과 비판은 제외; 국적·민족 자체를 이유로 하면 `identity` |
| `non_state_community` | 지지층·팬덤·이념 집단 | 정당 지지자·정치 팬덤·운동 진영 전체의 열등성 일반화, 추방·폭력 주장 | 특정 주장·시위·댓글 행동 비판은 제외; 정당·후보 자체는 `non_state_authority` |

### 표적과 잔여 판정

| 코드 | 포함 기준 | 제외·경계 |
| --- | --- | --- |
| `no_target` | 선행 대상이 없는 단독 욕설, 수집 문맥만으로 표적을 복원할 수 없는 공격·위협 | `profanity` 외 표적 category와 함께 사용할 수 없고 `target_group=null`이어야 함 |
| `other` | hate threshold는 충족하지만 직업·외모·경제적 지위 등 현재 taxonomy가 정의하지 않은 속성 공격 | 최후 수단이며 항상 단독 사용; 반복되는 표적은 taxonomy 개정 후보로 기록 |
| `unclassified` | 행위·정책 비판, 비동조 인용, 중립 정보, 질문, 공격으로 확정하기 어려운 표현 | `is_hate_speech=false`일 때만 단독 사용하며 `target_group`과 `hate_type`은 null |

복수 category는 서로 다른 공격 근거가 원문에 각각 있을 때만 선택한다. 같은 정치 표적을 `authority`와 `community`로 중복 선택하지 않고 실제 공격받는 단위를 우선한다. `other`와 `unclassified`는 항상 단독이다.

## 카테고리 선택 규칙

### 1. 비혐오 표현

비혐오 표현은 다음과 같이 저장한다.

```json
{
  "is_hate_speech": false,
  "categories": ["unclassified"],
  "target_group": null,
  "hate_type": null
}
```

`unclassified`는 보고서의 혐오 카테고리 분포 계산에서 제외한다.

### 2. 혐오 표현

혐오 표현은 하나 이상의 구체 카테고리를 선택한다.

```json
{
  "is_hate_speech": true,
  "categories": ["identity", "profanity"],
  "target_group": "중국인",
  "hate_type": "모욕/비하"
}
```

혐오 표현에는 `unclassified`를 함께 넣지 않는다.

### 3. 기타

`other`는 혐오표현으로 판단되지만 구체 카테고리에 넣을 수 없을 때만 사용한다.

`other`는 다른 카테고리와 함께 사용할 수 없다.

```json
{
  "is_hate_speech": true,
  "categories": ["other"],
  "target_group": "식별된 대상",
  "hate_type": "모욕/비하"
}
```

### 4. 대상 없음

`no_target`은 혐오적 표현이 있으나 공격 대상이 명시되지 않은 경우 사용한다.

욕설만 존재하고 대상이 없는 경우 `profanity`와 함께 사용할 수 있다.

```json
{
  "is_hate_speech": true,
  "categories": ["profanity", "no_target"],
  "target_group": null,
  "hate_type": "욕설"
}
```

### 5. 정치 혐오 카테고리

정치 혐오 카테고리는 대상의 유형과 행위자 성격을 함께 판단한다.

| 축 | 값 | 설명 |
| --- | --- | --- |
| 대상 유형 | `authority` | 개인, 조직, 기관, 지도부 등 권위체 |
| 대상 유형 | `regime` | 제도, 법, 정책, 절차, 규칙 |
| 대상 유형 | `community` | 국민, 지지층, 팬덤, 정치 커뮤니티 |
| 행위자 성격 | `state` | 국가기관 또는 법률상 공직자 |
| 행위자 성격 | `non_state` | 국가기관이 아닌 개인, 조직, 집단 |

두 축을 결합해 `state_authority`, `non_state_authority`, `state_regime`, `non_state_regime`, `state_community`, `non_state_community` 중 하나를 선택한다.

## 출력 필드 역할

| 필드 | 역할 |
| --- | --- |
| `is_hate_speech` | 혐오표현 여부 요약 |
| `categories` | 보고서와 평가의 핵심 분류 단위 |
| `target_group` | 공격 대상의 자연어 이름 |
| `hate_type` | 모욕, 비하, 멸시, 위협, 선동, 욕설 등 표현 방식 |
| `reasoning` | 카테고리 선택 근거 |
| `similar_cases_used` | 참고한 예시 corpus |
| `definition_docs_used` | 참고한 정의 문서 corpus |

`categories`는 통계와 필터링에 사용한다.

`target_group`과 `hate_type`은 카테고리 판단을 설명하는 보조 축으로 사용한다.

## 정답 데이터셋 정책

### UNSMILE 활용 범위

UNSMILE은 라이선스상 공개 또는 상업 retrieval corpus에 포함하지 않는다.

명시적 허가 전에는 내부 평가와 label mapping 참고에만 사용한다.

UNSMILE은 다음 내부 평가에 사용할 수 있다.

- 혐오/비혐오 기본 판정
- `gender`
- `age`
- `identity`
- `profanity`
- `other`

UNSMILE은 다음 평가에는 충분하지 않다.

- 정치 혐오 6개 카테고리
- `target_group`
- `hate_type`
- 보고서 대표 사례 품질
- 댓글 네트워크상의 카테고리 분포 타당성

### 서비스 전용 gold dataset

정치 혐오 카테고리를 주요 논점으로 삼으려면 YouTube 댓글과 스크립트에서 별도 gold dataset을 구축해야 한다.

최소 라벨 필드는 다음과 같다.

| 필드 | 설명 |
| --- | --- |
| `source_type` | `comment`, `reply`, `script_segment` |
| `source_id` | 원천 데이터 ID |
| `text` | 라벨링 대상 텍스트 |
| `is_hate_speech` | 혐오표현 여부 |
| `categories` | 허용 카테고리 목록 |
| `target_group` | 공격 대상 |
| `hate_type` | 표현 방식 |
| `rationale` | 사람이 작성한 판단 근거 |
| `taxonomy_version` | 적용한 카테고리 문서 버전 |
| `reviewed_at` | 검토 시각 |

MVP에서는 단일 검토자가 라벨링한 small gold set으로 시작할 수 있다.

운영 단계에서는 2인 이상 라벨링과 불일치 조정 절차를 추가한다.

## 평가 지표

카테고리가 주요 논점이므로 평가는 다음 계층으로 나눈다.

| 계층 | 평가 대상 | 지표 |
| --- | --- | --- |
| L1 | 혐오/비혐오 | binary F1, precision, recall |
| L2 | 기본 혐오 카테고리 | multi-label F1, category precision/recall |
| L3 | 정치 혐오 카테고리 | category별 F1, confusion matrix |
| L4 | target_group | exact match, 부분 일치 검토 |
| L5 | hate_type | controlled label accuracy |
| L6 | reasoning | 사람 검토 rubric |

보고서에는 최소 L1, L2, L3 결과를 구분해서 표시한다.

## 현재 프롬프트 판단 순서

`category-rag-v0.3.0` 프롬프트는 다음 순서를 따른다.

1. 혐오표현 여부를 판단한다.
2. 비혐오이면 `unclassified`를 반환한다.
3. 혐오이면 허용 카테고리 중 하나 이상을 선택한다.
4. 정치 혐오이면 대상 유형과 행위자 성격을 분리해 판단한다.
5. `target_group`, `hate_type`, `reasoning`을 함께 반환한다.

`hate_type`은 `모욕·비하`, `집단 일반화`, `비인간화`, `배제·차별`, `위협·폭력`, `제거·억압 선동`, `욕설` 중 핵심 표현 방식 1~2개를 한국어로 기록한다. `target_group`은 욕설을 제거한 간결한 한국어 명사구로 저장하며 원문보다 넓은 집단으로 일반화하지 않는다.

## 문서 정합성 영향

이 문서는 다음 문서의 기준 문서다.

- `02_hld.md`
- `03_data_model.md`
- `04_pipeline_jobs.md`
- `05_api_spec.md`
- `06_report_spec.md`
- `07_backend_design.md`
- `08_mvp_plan.md`
- `09_implementation_decisions.md`

후속 작업에서 위 문서들의 카테고리 표현을 이 문서 기준으로 정렬해야 한다.
