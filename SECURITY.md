# Security Policy

## Secret handling

- Secret 원문은 환경변수 또는 배포 플랫폼 secret manager로만 주입한다.
- `.env`, raw dataset, vector store, report export는 Git과 container build context에서 제외한다.
- 관리자 API는 `X-Admin-Token`을 constant-time 비교하며 secret 값은 응답에 포함하지 않는다.

## Dependency audit

CI는 `pip-audit`을 실행한다. 2026-07-11 기준 다음 항목만 명시적으로 예외 처리한다.

### `PYSEC-2026-311` / `CVE-2026-45829`

- 영향 기능: ChromaDB HTTP server의 인증 전 collection 생성 API에서 공격자가 embedding model repository와 `trust_remote_code=true`를 전달하는 경로
- 현재 구성: ChromaDB server를 실행하거나 외부에 노출하지 않는다. 애플리케이션 worker가 `PersistentClient`를 embedded mode로만 사용하며 embedding function은 시작 시 환경 설정으로 고정한다.
- 외부 입력 경계: 공개 API에는 Chroma tenant/database/collection 생성, model repository, `trust_remote_code` 입력 필드가 없다.
- 컨테이너 경계: worker는 non-root, production root filesystem은 read-only이고 Chroma/report 전용 volume만 쓸 수 있다.
- 잔여 위험: 취약 코드가 dependency에 포함되어 있으므로 upstream 수정 버전이 공개되면 즉시 lockfile을 갱신하고 audit 예외를 제거한다.
- 금지 사항: Chroma HTTP server mode 또는 Chroma port 공개는 수정 버전 적용 전 허용하지 않는다.

이 예외는 취약점이 없다는 의미가 아니라 현재 애플리케이션에서 취약 endpoint가 도달 불가능하다는 제한적 위험 수용이다.

## Reporting

취약점은 공개 issue에 secret이나 실제 사용자 데이터를 포함하지 말고 저장소 관리자에게 비공개로 전달한다.

Upstream 수정 버전이 공개되면 `pip-audit` 예외와 이 위험 수용 항목을 같은 변경에서 제거한다.
