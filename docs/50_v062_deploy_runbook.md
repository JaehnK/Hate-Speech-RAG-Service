# v0.6.2 운영 배포 절차

| 항목 | 값 |
| --- | --- |
| 작성일 | 2026-11-09 KST |
| 대상 커밋 | `main` (41c957b 이후, `.dockerignore` 수정 d5c254c 포함) |
| 바뀌는 것 | worker 기본 prompt `category-rag-v0.6.2`, taxonomy v0.5.1, 규범·기준 문서 corpus, 분석 방식(절약·기본, Haiku 5.5), 보고서 근거 인용 표시 |
| 결과 근거 | `docs/49_v062_benchmark_results.md`, 메모리 대응 `docs/51_example_index_memory.md` |

새 이미지는 taxonomy v0.5.1, 규범 corpus, 디스크 기반 유사 사례 인덱스가 벡터 저장소에 있어야 제대로 동작한다. 그래서 **저장소 교체(3단계)를 worker 교체(4단계)보다 먼저** 한다. 교체 중에는 worker를 멈춰 둔다.

## 0. 변수

```bash
PROJECT=hsr-portfolio-49143
REGION=us-central1
ZONE=us-central1-a
REG=$REGION-docker.pkg.dev/$PROJECT/hsr
TAG=v3   # frontend. backend는 v4(디스크 기반 유사 사례 인덱스, docs/51)
```

## 1. 이미지 빌드·푸시 (로컬, `main`에서)

로컬 빌드로 확인한 backend 이미지는 619MB이고, 규범 corpus 58 chunk와 기본 prompt `category-rag-v0.6.2`가 들어 있다. `.dockerignore`가 `.chroma*`를 모두 제외해야 실험용 벡터 저장소 사본이 이미지에 들어가지 않는다.

```bash
gcloud auth configure-docker $REGION-docker.pkg.dev
docker build -f Dockerfile.backend -t $REG/backend:v4 .
docker build -f Dockerfile.frontend --target production -t $REG/frontend:$TAG .
docker push $REG/backend:v4
docker push $REG/frontend:$TAG
```

## 2. TypeSafe 키를 Secret Manager에 등록 (절약 방식용)

```bash
printf '%s' "<TYPESAFE_API_KEY 값>" | gcloud secrets create typesafe-api-key --project $PROJECT --data-file=-
gcloud secrets add-iam-policy-binding typesafe-api-key --project $PROJECT \
  --member="serviceAccount:$(gcloud run services describe web --region $REGION --project $PROJECT --format='value(spec.template.spec.serviceAccountName)')" \
  --role=roles/secretmanager.secretAccessor
```

서비스 계정 이름이 비어 나오면 기본 compute 서비스 계정(`<프로젝트번호>-compute@developer.gserviceaccount.com`)을 쓴다.

## 3. 벡터 저장소: 로컬에서 만들어 VM에 올리기

> 2026-11-11 변경. VM(RAM 969MB)에서 직접 재매핑·적재하면 Chroma가 유사 사례 인덱스 2.9GB를 메모리에 올려 VM이 멈춘다(docs/51). 저장소는 로컬에서 완성하고, 유사 사례는 디스크 기반 인덱스로 바꿔서 올린다. **backend 이미지는 `v4`부터** 이 인덱스를 읽는다.

### 3-1. 로컬: 저장소 만들기

운영 저장소 사본(`.chroma-prod`)에서 시작한다. 재매핑은 이미 적용되어 있다(변경 0건).

```bash
cp -a .chroma-prod .chroma-v3
uv run python -m app.analysis.rag_ingest --persist-directory .chroma-v3 --reset --embedding-provider upstage
uv run python -c "
import os
from app.analysis.definition_ingest import ingest_manifest_definitions
from app.analysis.embeddings import create_embedding_function
ef = create_embedding_function(provider='upstage', model='embedding', api_key=os.environ['UPSTAGE_API_KEY'])
print(ingest_manifest_definitions('data/external/manifests/dataset_sources.yaml', '.chroma-v3', embedding_function=ef, reset=True))
"
uv run python -m app.analysis.normative_corpus --persist-directory .chroma-v3 --embedding-provider upstage

# 배포용: taxonomy 21 + authoritative 66만 Chroma에, 유사 사례 172,157은 디스크 인덱스로
uv run python -m scripts.shrink_example_store --source .chroma-v3 --target .chroma-v3m --size 0
uv run python -m app.analysis.example_index --source .chroma-v3 --target .chroma-v3m/example_index
tar -cf chroma-v3m.tar -C .chroma-v3m . && sha256sum chroma-v3m.tar | cut -c1-16
gcloud compute scp chroma-v3m.tar hsr-vm:~/ --zone $ZONE --project $PROJECT
```

### 3-2. VM: 교체

```bash
gcloud compute ssh hsr-vm --zone $ZONE --project $PROJECT
```

VM 안에서 실행한다. swap 2GB(`/swapfile`)와 백업 `/opt/hsr/backups/chroma-20261109-pre-v062`는 2026-11-09에 만들어 두었다.

```bash
sudo docker stop hsr-worker-1 2>/dev/null
sha256sum ~/chroma-v3m.tar | cut -c1-16          # 3-1에서 본 값과 같아야 함
V=/var/lib/docker/volumes/hsr_chroma_data/_data
sudo rm -rf $V && sudo mkdir -p $V && sudo tar -xf ~/chroma-v3m.tar -C $V && rm ~/chroma-v3m.tar

NEW=us-central1-docker.pkg.dev/hsr-portfolio-49143/hsr/backend:v4
sudo docker pull $NEW
# 확인: taxonomy 21, authoritative 66, examples 0(Chroma), example_index 172157
sudo docker run --rm -v hsr_chroma_data:/data/chroma --entrypoint python $NEW -c "
import chromadb
from app.analysis.example_index import ExampleIndex
c = chromadb.PersistentClient(path='/data/chroma')
print({n: c.get_collection(n).count() for n in ['hate_speech_taxonomy', 'hate_speech_authoritative', 'hate_speech_examples']})
print('example_index', ExampleIndex('/data/chroma/example_index').count())
"
```

## 4. VM: worker 교체

`/opt/hsr/.env`를 수정한다.

```bash
IMG_BACKEND=us-central1-docker.pkg.dev/hsr-portfolio-49143/hsr/backend:v4
RAG_EXECUTION_MODE=sequential
RAG_LLM_CONCURRENCY=2
JEV_PREFILTER_ENABLED=true
TYPESAFE_API_KEY=<값>
UPSTAGE_API_KEY=<운영 upstage-api-key secret 값>
```

v3부터 사용자는 Anthropic 키만 등록하고, 임베딩은 서버 키로 처리한다. worker에 `UPSTAGE_API_KEY`가 없으면 시작할 때 설정 오류로 멈춘다. 값은 `gcloud secrets versions access latest --secret=upstage-api-key --project hsr-portfolio-49143`로 로컬에서 확인한다. e2-micro라 동시 처리는 낮게 둔다. 6단계에서 메모리를 보고 올린다.

로컬에서 새 `compose.yaml`(Jev 환경 변수 전달 포함)을 VM에 올리고 worker를 다시 띄운다.

```bash
# 로컬
gcloud compute scp compose.yaml compose.vm.yaml hsr-vm:/tmp/ --zone $ZONE --project $PROJECT
# VM
sudo cp /tmp/compose.yaml /tmp/compose.vm.yaml /opt/hsr/
cd /opt/hsr
sudo docker compose -f compose.yaml -f compose.vm.yaml run --rm migrate
sudo docker compose -f compose.yaml -f compose.vm.yaml up -d worker
sudo docker exec hsr-worker-1 env | grep -E "RAG_|JEV_"
```

## 5. Cloud Run 교체 (로컬)

```bash
gcloud run deploy web --region $REGION --project $PROJECT --image $REG/backend:v4 \
  --update-env-vars JEV_PREFILTER_ENABLED=true \
  --update-secrets TYPESAFE_API_KEY=typesafe-api-key:latest
gcloud run deploy frontend --region $REGION --project $PROJECT --image $REG/frontend:$TAG
```

`web`의 `JEV_PREFILTER_ENABLED`는 분석 화면에 절약 방식을 보여줄지 정하고, 실제 Jev 호출은 worker가 한다. 두 곳 모두 켜야 한다.

## 5-1. 도메인 확인 (hatescope.jaehunk.com)

운영 도메인이 `haterag.jaehunk.com`에서 `hatescope.jaehunk.com`으로 바뀌었다. 코드에 도메인을 하드코딩한 곳은 없고 아래 값만 맞으면 된다.

```bash
gcloud run services describe web --region $REGION --project $PROJECT \
  --format='value(spec.template.spec.containers[0].env)' | tr ';' '\n' | grep -E "FRONTEND_ORIGIN|GOOGLE_OAUTH_REDIRECT_URI"
# 다르면
gcloud run services update web --region $REGION --project $PROJECT \
  --update-env-vars FRONTEND_ORIGIN=https://hatescope.jaehunk.com,GOOGLE_OAUTH_REDIRECT_URI=https://hatescope.jaehunk.com/api/auth/google/callback
```

- Google Cloud Console → OAuth 클라이언트의 승인된 리디렉션 URI에 `https://hatescope.jaehunk.com/api/auth/google/callback`가 있어야 한다. 승인된 JavaScript 원본도 같은 도메인으로 맞춘다.
- `FRONTEND_ORIGIN`이 다르면 로그인 후 분석 요청 같은 상태 변경 API가 Origin 검증에서 403으로 막힌다.
- 옛 도메인을 잠시 유지하려면 리디렉션 URI에 두 도메인을 모두 등록해 두고, `FRONTEND_ORIGIN`은 새 도메인 하나로 둔다.

## 6. 확인

```bash
curl -s https://hatescope.jaehunk.com/api/analysis-jobs/tiers | python3 -m json.tool   # economy, standard
```

- 분석 화면에 절약·기본 두 카드와 정확도·비용이 보인다.
- 작은 영상으로 분석 1회: 보고서의 "판정 근거 기준"에 심의규정·인권위 기준 제목과 원문 링크가 보인다.
- 분석 중 VM에서 `free -m`과 `sudo docker stats --no-stream`으로 최대 메모리를 확인한다. swap 사용이 늘지 않으면 `RAG_EXECUTION_MODE=parallel`, 동시 처리 2 → 4로 올린다.

## 7. 공개 샘플 교체

1. 기존 공개 샘플과 같은 영상을 새 버전으로 분석한다.
2. 새 report를 공개 샘플로 지정하고 기존 샘플을 해제한다(관리자 API, `X-Admin-Token`).
3. 비로그인 상태로 `/samples`에서 새 보고서를 확인한다.

## 되돌리기

v2 저장소도 유사 사례 인덱스가 2.9GB라 e2-micro에서 분석 중 멈출 수 있다(docs/51). 되돌리기는 v4 자체에 결함이 있을 때만 쓴다.

```bash
# VM
sudo docker stop hsr-worker-1
sudo rm -rf /var/lib/docker/volumes/hsr_chroma_data/_data
sudo cp -a /opt/hsr/backups/chroma-20261109-pre-v062 /var/lib/docker/volumes/hsr_chroma_data/_data
# .env의 IMG_BACKEND를 backend:v2로 되돌린 뒤
sudo docker compose -f compose.yaml -f compose.vm.yaml up -d worker
# 로컬
gcloud run deploy web --region $REGION --project $PROJECT --image $REG/backend:v2
gcloud run deploy frontend --region $REGION --project $PROJECT --image $REG/frontend:v2
```

## 부록: 1비트 유사 사례 인덱스 전환 (backend:v5, 2026-11-12)

v4의 int8 인덱스는 VM 캐시에 들어가지 않아 댓글 1개에 수십 초가 걸렸다(docs/51 4절). v5는 기존 float16 벡터로 1비트 인덱스를 VM에서 직접 만든다. 업로드할 파일은 없다.

```bash
# VM
NEW=us-central1-docker.pkg.dev/hsr-portfolio-49143/hsr/backend:v5
sudo docker pull $NEW
sudo docker stop hsr-worker-1
sudo docker run --rm -v hsr_chroma_data:/data/chroma --entrypoint python $NEW -m app.analysis.example_index --from-vectors /data/chroma/example_index
sudo docker run --rm -v hsr_chroma_data:/data/chroma --entrypoint python $NEW -m app.analysis.example_index --benchmark /data/chroma/example_index
# .env의 IMG_BACKEND를 backend:v5로 바꾼 뒤
cd /opt/hsr && sudo docker compose -f compose.yaml -f compose.vm.yaml up -d worker
```

v4로 되돌릴 때는 `IMG_BACKEND`만 v4로 바꾼다. v4는 `examples.usearch`(int8)를 그대로 읽는다.

## 부록: 프롬프트 v0.7.0 · taxonomy v0.6.0 (backend:v6, frontend:v5, 2026-11-12)

v6는 기본 프롬프트가 `category-rag-v0.7.0`이고, 판정 기준 카드(taxonomy v0.6.0)가 벡터 저장소에 있어야 한다(docs/52). 그래서 **taxonomy 재적재를 worker 교체보다 먼저** 한다. taxonomy 컬렉션(21건)만 다시 만들고 규범 문서와 유사 사례 인덱스는 그대로 둔다. v5 부록(1비트 인덱스)을 아직 적용하지 않았다면 그 `--from-vectors` 단계를 먼저 한다. v6 이미지로 실행해도 된다.

```bash
# VM
NEW=us-central1-docker.pkg.dev/hsr-portfolio-49143/hsr/backend:v6
sudo docker pull $NEW
sudo docker stop hsr-worker-1
sudo docker run --rm --env-file /opt/hsr/.env -v hsr_chroma_data:/data/chroma --entrypoint python $NEW \
  -m app.analysis.rag_ingest --persist-directory /data/chroma --embedding-provider upstage --reset
# 출력의 document_count 21, corpus_version definition-corpus-2026-11-12-v0.6.0 확인
# .env의 IMG_BACKEND를 backend:v6로 바꾼 뒤
cd /opt/hsr && sudo docker compose -f compose.yaml -f compose.vm.yaml up -d worker

# 로컬
gcloud run deploy web --region $REGION --project $PROJECT --image $REG/backend:v6
gcloud run deploy frontend --region $REGION --project $PROJECT --image $REG/frontend:v5
```

새 보고서부터 "혐오표현 (집단 대상)"과 "모욕·욕설 (개인 대상)"이 나뉜다. 기존 보고서는 예전 화면 그대로다.

되돌리기: `IMG_BACKEND`를 v5로 바꾸고 v5 이미지로 같은 `rag_ingest` 명령을 실행해 taxonomy v0.5.1을 다시 적재한다. v6의 카드가 남아 있어도 v0.6.2는 동작하지만, 판정 기준이 v0.6.0으로 바뀐 상태가 된다.
