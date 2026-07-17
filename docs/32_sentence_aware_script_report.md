# 문장 경계 우선 자막 분석과 보고서 노출

## 목표

- 자막을 사람이 검토하기 좋은 발화 단위로 분할한다.
- 저장된 자막 RAG 판정을 보고서 화면에서 시간순으로 확인한다.
- 기존 API·DB 스키마와 과거 보고서를 깨뜨리지 않는다.

## 판단

YouTube 자막 cue는 문장과 일치하지 않고, 자동 자막은 문장부호가 없는 경우가 많다. 따라서 cue 하나를 문장 하나로 간주하지 않는다.

분할 규칙은 다음 순서를 따른다.

1. cue를 시간순으로 누적한다.
2. `.`, `?`, `!`, `…`, `。`, `？`, `！`로 끝나는 cue에서 segment를 마감한다.
3. 종결부호가 없어도 45초 또는 800자를 넘기기 전에 segment를 마감한다.
4. 분할 전략은 transcript snapshot의 `raw_payload.segmentation`에 기록한다.

이는 문장 경계를 우선하는 규칙이지 언어학적 문장 분리기가 아니다. 한 cue 내에 여러 문장이 있어도 임의로 타임스탬프를 추정하지 않는다.

## 프론트엔드

보고서의 `자막 RAG 분석` 영역은 기존 `GET /api/reports/{report_id}/script-segments` API를 사용한다.

- 시작–종료 시간
- 자막 원문
- 정상·혐오표현·분석 실패 상태
- canonical 카테고리의 한국어 label
- RAG 분석 사유
- 200건 단위 pagination과 추가 불러오기
- 자막 없음, loading, API 오류 상태

## 호환성

- DB migration과 API 응답 스키마 변경은 없다.
- 기존 보고서의 segment도 그대로 화면에 표시된다.
- 문장 경계 우선 분할은 변경 이후 새로 수집된 job에만 적용된다. 기존 job을 자동 재분석하지 않는다.

## 작업 순서와 검증

1. 기존 collector·API·report UI 계약 확인
2. 문장 경계 우선 분할과 strategy metadata 구현
3. 문장 경계·기존 시간 fallback 단위 테스트
4. 자막 API type·client·pagination·report panel 구현
5. 시간 표시 helper 단위 테스트
6. 프론트 전체 테스트·production build, 백엔드 관련 테스트, Ruff, diff 정합성 검증
7. feature branch commit 후 `main` 병합, branch 유지

검증 결과:

- backend: `102 passed, 1 skipped`
- frontend: `5 files, 13 tests passed`
- frontend TypeScript/Vite production build 통과
- Ruff, Python compileall, `git diff --check` 통과
- dev·test·prod Compose config 통과
- web·worker·frontend production image build 통과
