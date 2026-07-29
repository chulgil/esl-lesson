# 품질 계약 (Harness Contract)

> 이 프로젝트에 적용되는 품질 기준. `cg-brownfield-scan` 또는 첫 `cg-spec-and-harness` 실행 시 자동으로 초안이 작성됩니다.

## 린팅

- 린터: (프로젝트에 맞게 작성)
- 허용되지 않는 규칙 예외:

## 테스팅

- 단위 테스트 프레임워크:
- E2E 프레임워크:
- 최소 커버리지: 80%

## 아키텍처 규칙

- (예) 모든 도메인 로직은 `features/{domain}/domain/` 이하에만 작성
- (예) UI 에서 repository 직접 호출 금지

## Evaluation Pipeline (3-Critic)

| Critic | 역할 | 독립성 |
|--------|------|--------|
| Code Critic | spec 정렬, 보안, 엣지 케이스 | 작성자와 다른 세션 |
| Test Critic | Oracle Problem 점검 (의도 vs 구현 검증) | 코드 작성자와 다른 세션 — **필수** |
| E2E Eval | 스크립트 + 에이전트 탐색 E2E | Playwright MCP 또는 수동 |

Oracle Problem: 같은 AI가 코드+테스트를 쓰면 실제 의도가 아닌 구현 그대로를 테스트하게 되어 정확도가 낮아집니다. Test critic 은 반드시 코드 세션과 분리하세요.
