# 유사 사례 인덱스를 디스크 기반으로 교체

| 항목 | 값 |
| --- | --- |
| 작성일 | 2026-11-11 KST |
| 계기 | v0.6.2 배포 중 VM(e2-micro, RAM 969MB)이 저장소 작업에서 두 번 멈춤 |
| 결론 | 유사 사례 17만 건을 Chroma 대신 usearch(int8, 메모리 매핑) + float16 재정렬로 검색한다. 정확도는 같고 메모리는 2.9GB → 350MB 이하 |

## 1. 원인

Chroma는 컬렉션을 건드리는 순간(개수 세기 포함) 그 컬렉션의 HNSW 인덱스 전체를 메모리에 올린다.

| 작업 | 최대 메모리 |
| --- | ---: |
| taxonomy 컬렉션 열기 | 0.1GB |
| 유사 사례 컬렉션 열기(172,157건 × 4096차원) | 2.9GB |

VM은 RAM 969MB, swap 2GB라 저장소 작업과 worker의 유사 사례 검색 모두 swap을 붙잡고 멈춘다. v2 저장소도 크기가 같았다(3.9GB). 운영 분석 이력이 1건뿐이라 드러나지 않았을 뿐, v2부터 있던 문제다.

## 2. 검토한 방법

### 2-1. 유사 사례 축소 (기각)

범주별 하한을 두고 층화 추출해 17,157건(10%)으로 줄였다. LLM 없이 잰 근접 사례 다수결 F1은 그대로였지만(0.849 → 0.851), dev 1,000건 실제 판정은 나빠졌다.

| 저장소 | precision | recall | F1 |
| --- | ---: | ---: | ---: |
| 원본 172,157건 | 0.945 | 0.741 | 0.831 |
| 축소 17,157건 | 0.937 | 0.706 | 0.806 |

한쪽만 맞힌 문항이 53 : 25(McNemar p=0.002)로, 축소본이 혐오를 놓치는 쪽으로 기울었다. 모델이 거의 같은 문장의 사례에 기대는데, 축소하면 그런 사례가 빠지는 것으로 본다. 검색 품질 지표만으로는 판정 영향을 예측할 수 없었다.

### 2-2. 디스크 기반 인덱스 (채택)

- usearch HNSW 인덱스를 int8로 저장하고 `view=True`로 메모리 매핑한다. 검색이 방문하는 페이지만 읽는다.
- int8 검색으로 후보 48건을 뽑고, float16 원본 벡터(역시 메모리 매핑)로 정확한 cosine 유사도를 계산해 상위 6건을 고른다.
- 문서와 메타데이터는 SQLite에 둔다. 검색 결과는 Chroma `query`와 같은 형태라 retriever와 파싱 코드는 그대로다.
- 저장소에 `example_index/`가 있으면 retriever가 이것을 쓰고, 없으면 기존 Chroma 컬렉션을 쓴다.

## 3. 결과

### 검색 품질 (dev 300건, 정확한 전수 검색 대비 recall@6)

| 인덱스 | recall@6 |
| --- | ---: |
| Chroma HNSW (기존) | 0.858 |
| usearch int8만 | 0.786 (탐색 폭 128) / 0.831 (512) |
| usearch int8 후보 48 + float16 재정렬 (채택) | 0.936 |

### 정확도 (dev 1,000건, Haiku 5.5, v0.6.2)

| 인덱스 | precision | recall | F1 | category macro F1 |
| --- | ---: | ---: | ---: | ---: |
| Chroma (기존) | 0.945 | 0.741 | 0.831 | 0.563 |
| 디스크 인덱스 | 0.950 | 0.737 | 0.830 | 0.577 |

한쪽만 맞힌 문항이 17 : 17(p=1.0)로 차이가 없다. docs/49의 test 결과는 그대로 유효하다고 본다.

### 메모리와 속도

| 항목 | 값 |
| --- | --- |
| 메모리 350MB 제한, swap 0에서 retriever 검색 300회 | 실패 0, 1회 약 19ms(taxonomy·규범 문서 검색 포함) |
| 저장소 크기 | 3.9GB → 2.2GB(int8 인덱스 0.7GB, float16 벡터 1.4GB, 메타데이터 0.12GB, 나머지 Chroma) |

## 4. 재현

```bash
# 유사 사례를 뺀 Chroma 저장소(taxonomy, authoritative만 복사)
uv run python -m scripts.shrink_example_store --source .chroma-v3 --target .chroma-v3m --size 0
# 디스크 기반 유사 사례 인덱스
uv run python -m app.analysis.example_index --source .chroma-v3 --target .chroma-v3m/example_index
# 축소 실험(2-1)의 검색 품질 비교
uv run python -m experiments.example_store_probe --store <저장소>
```
