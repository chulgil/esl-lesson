---
name: security-pipeline
description: 보안 파이프라인 - CWE Top 25 + STRIDE 자동 검증
version: 2.0.0
---

## Overview

보안 파이프라인 스킬은 코드 변경 시 자동으로 CWE Top 25 기반 보안 검증을 수행한다.
`/handoff-verify --security`, `/commit-push-pr` 실행 시 통합 동작한다.
보안 체크리스트 참조: `~/.claude/skills/_reference/security-checklist.md`

effort:max가 항상 강제 적용된다. 보안 검증은 축약하지 않는다.

---

## Trigger Conditions

### 파일 패턴 기반 자동 트리거

다음 패턴을 포함하는 파일이 변경되면 보안 파이프라인이 자동으로 실행된다:

| 패턴 | 트리거 수준 | 설명 |
|------|-------------|------|
| `**/auth/**` | Full Scan | 인증 관련 모듈 |
| `**/payment/**` | Full Scan | 결제 처리 모듈 |
| `**/api/**` | CWE Scan | API 엔드포인트 |
| `**/middleware/**` | CWE Scan | 미들웨어 |
| `**/session*` | CWE Scan | 세션 관리 |
| `**/token*` | CWE Scan | 토큰 처리 |
| `**/crypto*` | CWE Scan | 암호화 로직 |
| `**/admin/**` | Full + STRIDE | 관리자 기능 |
| `**/upload*` | CWE Scan | 파일 업로드 |
| `**/.env*` | Credential Scan | 환경변수 파일 |
| `**/config/secret*` | Credential Scan | 시크릿 설정 |

### 커밋 기반 자동 트리거

`/commit-push-pr` 실행 시 staged 파일 목록에서 위 패턴이 감지되면,
커밋 전 보안 파이프라인이 자동으로 실행된다.

---

## CWE Scanning Rules

CWE Top 25 를 3단계 심각도로 분류해 grep 패턴으로 매칭한다:

- **Critical (커밋 차단)** — CWE-89 SQLi, CWE-79 XSS, CWE-78/77 Command Injection, CWE-798 Hardcoded Credentials.
- **High (경고, 커밋 허용)** — CWE-22 Path Traversal, CWE-352 CSRF, CWE-287/862 Auth, CWE-502 Deserialization, CWE-918 SSRF, CWE-434 Upload, CWE-269 Privilege Escalation.
- **Medium (정보 제공)** — CWE-200 Info Disclosure, CWE-20 Input Validation, CWE-327 Broken Crypto, CWE-276 Incorrect Perms.

각 항목의 정확한 grep 패턴: [reference.md](reference.md) §CWE Scanning Rules.

---

## Auto-Fix Rules

자동 수정은 사용자 승인 후, 신뢰도 High 항목만 적용한다. 대상: Parameterized Queries
(CWE-89), Environment Variables (CWE-798), Safe DOM (CWE-79), Remove Sensitive Logs
(CWE-200), Secure Hash (CWE-327). before/after 예시: [reference.md](reference.md) §Auto-Fix Rules.

---

## Integration Points

### /handoff-verify (v6)

`/handoff-verify` 커맨드의 검증 단계에서 보안 검사가 포함된다.
verify-agent가 민감 파일 변경을 감지하면 이 스킬을 자동 호출한다.

### /commit-push-pr

커밋 전 자동 보안 게이트로 동작한다:
- Critical 발견 시: 커밋 차단 (BLOCKED)
- High 발견 시: 경고 표시 후 사용자 확인 (WARN)
- Medium 이하만 존재: 통과 (PASS)

### /security-review (통합됨)

이전 security-review 스킬의 OWASP 체크리스트는 `_reference/security-checklist.md`로 전환.
전체 보안 리뷰 시 이 스킬의 CWE Top 25 매핑 + STRIDE + 의존성 검사가 수행되며,
체크리스트 참조 파일을 함께 로드한다.

---

## effort:max Enforcement

이 스킬은 항상 effort:max로 실행된다.
보안 검증에서 분석 깊이를 줄이는 것은 허용하지 않는다.

적용 범위:
- CWE 패턴 매칭 시 false positive 최소화를 위한 컨텍스트 분석
- STRIDE 분류 시 전체 데이터 흐름 추적
- 자동 수정 제안 시 사이드 이펙트 검증
- 의존성 검사 시 transitive dependency 포함
