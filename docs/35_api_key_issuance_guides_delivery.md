# API 키 발급 안내 구현 기록

## 목표

로그인 후 `/settings`에서 사용자가 별도 검색 없이 Anthropic과 Upstage API 키를 발급하고 등록할 수 있게 한다. 키 원문을 서비스 문서나 로그에 남기지 않는 기존 BYOK 보안 경계는 유지한다.

## 구현 브랜치

- `feat/api-key-issuance-guides`

## 공식 경로 확인

2026-07-17 기준 각 공급자의 공식 사이트에서 다음 경로를 확인했다.

- Anthropic: `https://platform.claude.com/settings/keys`
- Upstage: `https://console.upstage.ai/api-keys`

Anthropic Help Center는 Claude Console에서 API 키 생성과 결제를 관리하며 일반 Claude 구독과 API 사용이 별도임을 안내한다. Upstage Console은 API Keys 화면과 Billing/Usage 메뉴를 제공한다.

## 변경 시퀀스

1. 기존 공급자별 키 등록 카드를 유지했다.
2. 각 카드에 공식 발급 페이지, 3단계 발급 절차, 결제·사용량 확인 안내를 추가했다.
3. 외부 링크는 새 탭에서 열고 현재 페이지에 대한 제어권을 주지 않도록 `rel="noreferrer"`를 적용했다.
4. 키를 Git, 메신저, 스크린샷에 남기지 말라는 공통 보안 안내를 입력란 위에 배치했다.
5. 공식 링크와 핵심 안내 문구가 렌더링되는지 frontend 테스트로 고정했다.

## 변경하지 않은 경계

- 키 저장 API와 provider 유효성 검증 방식
- Fernet 암호화와 fingerprint 응답
- 분석 job에서만 키를 복호화하는 worker 경계
- 키 삭제와 재검증 흐름

## 검증 기준

- 두 공식 링크가 정확한 URL과 안전한 새 탭 속성으로 렌더링된다.
- desktop에서는 두 카드가 나란히, mobile에서는 기존 breakpoint에 따라 한 열로 표시된다.
- frontend 전체 테스트와 TypeScript/Vite production build가 성공한다.
- `git diff --check`가 성공한다.

## 검증 결과

- frontend: `6 files`, `14 passed`
- TypeScript/Vite production build: 성공
- `git diff --check`: 성공
