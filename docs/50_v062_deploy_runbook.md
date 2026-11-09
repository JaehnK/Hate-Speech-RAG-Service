# v0.6.2 운영 배포 절차

| 항목 | 값 |
| --- | --- |
| 작성일 | 2026-11-09 KST |
| 대상 커밋 | `main` (41c957b 이후, `.dockerignore` 수정 d5c254c 포함) |
| 바뀌는 것 | worker 기본 prompt `category-rag-v0.6.2`, taxonomy v0.5.1, 규범·기준 문서 corpus, 분석 방식(절약·기본, Haiku 5.5), 보고서 근거 인용 표시 |
| 결과 근거 | `docs/49_v062_benchmark_results.md` |

새 이미지는 taxonomy v0.5.1과 규범 corpus가 벡터 저장소에 있어야 제대로 동작한다. 그래서 **저장소 적재(3단계)를 worker 교체(4단계)보다 먼저** 한다. 적재 중에는 worker를 멈춰 둔다.

## 0. 변수

```bash
PROJECT=hsr-portfolio-49143
REGION=us-central1
ZONE=us-central1-a
REG=$REGION-docker.pkg.dev/$PROJECT/hsr
TAG=v3
```

## 1. 이미지 빌드·푸시 (로컬, `main`에서)

로컬 빌드로 확인한 backend 이미지는 619MB이고, 규범 corpus 58 chunk와 기본 prompt `category-rag-v0.6.2`가 들어 있다. `.dockerignore`가 `.chroma*`를 모두 제외해야 실험용 벡터 저장소 사본이 이미지에 들어가지 않는다.

```bash
gcloud auth configure-docker $REGION-docker.pkg.dev
docker build -f Dockerfile.backend -t $REG/backend:$TAG .
docker build -f Dockerfile.frontend --target production -t $REG/frontend:$TAG .
docker push $REG/backend:$TAG
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

## 3. VM: 백업, 설정, 저장소 적재

```bash
gcloud compute ssh hsr-vm --zone $ZONE --project $PROJECT
```

VM 안에서 실행한다.

```bash
cd /opt/hsr
REG=us-central1-docker.pkg.dev/hsr-portfolio-49143/hsr
NEW=$REG/backend:v3

# 3-1. swap 2GB (메모리 969MB, swap 없음)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 3-2. worker 정지와 벡터 저장소 백업
sudo docker stop hsr-worker-1
sudo mkdir -p /opt/hsr/backups
sudo cp -a /var/lib/docker/volumes/hsr_chroma_data/_data /opt/hsr/backups/chroma-20261109-pre-v062

# 3-3. 새 이미지 받기
sudo docker pull $NEW

# 3-4. 적재에 쓸 Upstage 키 (운영 secret)
UPSTAGE=$(gcloud secrets versions access latest --secret=upstage-api-key --project hsr-portfolio-49143)
# VM 서비스 계정에 Secret Manager 권한이 없어 실패하면, 로컬에서 값을 확인해 직접 넣는다:
#   (로컬) gcloud secrets versions access latest --secret=upstage-api-key --project hsr-portfolio-49143
#   (VM)   read -rs UPSTAGE

run() { sudo docker run --rm -v hsr_chroma_data:/data/chroma -e UPSTAGE_API_KEY="$UPSTAGE" \
  -e EMBEDDING_PROVIDER=upstage --entrypoint python "$NEW" "$@"; }

# 3-5. K-HATERS category 재매핑 (docs/46). 이미 적용됐으면 changed 0
run -m scripts.remap_example_categories --persist-directory /data/chroma
run -m scripts.remap_example_categories --persist-directory /data/chroma --apply

# 3-6. taxonomy v0.5.1 (21 문서)
run -m app.analysis.rag_ingest --persist-directory /data/chroma --reset --embedding-provider upstage

# 3-7. authoritative: K-HATERS README 8 + 규범 corpus 58 = 66
run -c "
import os
from app.analysis.definition_ingest import ingest_manifest_definitions
from app.analysis.embeddings import create_embedding_function
ef = create_embedding_function(provider='upstage', model='embedding', api_key=os.environ['UPSTAGE_API_KEY'])
print(ingest_manifest_definitions('data/external/manifests/dataset_sources.yaml', '/data/chroma', embedding_function=ef, reset=True))
"
run -m app.analysis.normative_corpus --persist-directory /data/chroma --embedding-provider upstage

# 3-8. 확인: taxonomy 21, authoritative 66, examples 172157
run -c "
import chromadb
c = chromadb.PersistentClient(path='/data/chroma')
print({n: c.get_collection(n).count() for n in ['hate_speech_taxonomy', 'hate_speech_authoritative', 'hate_speech_examples']})
"
```

## 4. VM: worker 교체

`/opt/hsr/.env`를 수정한다.

```bash
IMG_BACKEND=us-central1-docker.pkg.dev/hsr-portfolio-49143/hsr/backend:v3
RAG_EXECUTION_MODE=parallel
RAG_ITEM_CONCURRENCY=4
RAG_EMBEDDING_CONCURRENCY=4
RAG_LLM_CONCURRENCY=4
JEV_PREFILTER_ENABLED=true
TYPESAFE_API_KEY=<값>
UPSTAGE_API_KEY=<운영 upstage-api-key secret 값>
```

v3부터 사용자는 Anthropic 키만 등록하고, 임베딩은 서버 키로 처리한다. worker에 `UPSTAGE_API_KEY`가 없으면 시작할 때 설정 오류로 멈춘다. 값은 3-4에서 받은 `$UPSTAGE`와 같다.

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
gcloud run deploy web --region $REGION --project $PROJECT --image $REG/backend:$TAG \
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
- 분석 중 VM에서 `free -m`과 `sudo docker stats --no-stream`으로 최대 메모리를 확인한다. 여유가 있으면 동시 처리 4 → 8.

## 7. 공개 샘플 교체

1. 기존 공개 샘플과 같은 영상을 새 버전으로 분석한다.
2. 새 report를 공개 샘플로 지정하고 기존 샘플을 해제한다(관리자 API, `X-Admin-Token`).
3. 비로그인 상태로 `/samples`에서 새 보고서를 확인한다.

## 되돌리기

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
