---
description: 현재 변경에 Code Critic 을 수행. spec 정렬 / 엣지케이스 / 보안 / 경계 검증.
---

# /code-review

## 용도

Phase 6 의 Code Critic 을 **커밋 직전** 에 호출합니다.
코드 작성자와 **별개 컨텍스트** 로 평가해야 Oracle Problem 을 피할 수 있습니다.

## 실행 방식 (필수) — Writer ≠ Evaluator 게이트

**Agent 도구로 격리 호출이 강제 조건**. 메인 세션에서 직접 리뷰 시도하면
자기확신 편향으로 버그 발견율이 60% 이상 떨어진다 (Anthropic 하네스 연구).

호출 전 체크리스트 (모두 만족해야 진행):
- [ ] Agent 도구 호출인가? (인라인 직접 평가 금지)
- [ ] 프롬프트 첫 줄에 `당신은 Code Critic 입니다. 작성자가 아닙니다.` 포함했는가?
- [ ] 입력은 **파일 경로** 로만 전달했는가? (diff 인라인 첨부 금지)
- [ ] 결과 200단어 이내 + Verifier 역할 명시 (`rules/subagent-output.md`)?

```
Agent(
  description="Code Critic — 현재 diff 평가 (작성자 격리)",
  subagent_type="general-purpose",
  prompt="""
  당신은 Code Critic 입니다. 작성자가 아닙니다.

  입력:
  - git diff (스테이지 + 워킹) — 직접 실행해서 확인
  - spec: .harness/spec/{...}.md

  평가 항목 (아래 표 참조).
  결과는 200단어 이내 구조화 포맷. 역할: Verifier.
  """
)
```

위반 시 차단 + Escalation 사다리:
- Critic 응답이 1인칭 ("내가 추가한", "방금 작성한") 사용 → 평가 무효, 1회 재실행
- 작성 세션의 주석/어휘 스타일을 그대로 반복 → 편향 의심, 1회 재실행
- 한 메시지에서 Critic 2개 이상 동시 호출 → 각각 독립 Agent 로 분리

재실행 후에도 같은 위반이 재발하면 무한 루프 방지를 위해 다음 순서로 escalate:
1. **2회차 위반**: 다른 `subagent_type` 으로 교체 (예: `general-purpose` → `test-critic`).
2. **3회차 위반**: 7-Phase 강제 회귀 (`cg-execution-loop` §7-Phase 회귀 트리거 발동) + 사용자 보고. PGE 경량 모드였다면 종료.
3. **사용자 명시적 우회 지시 시에만** 평가 생략 가능. 자동 통과 금지.

## 입력

- `git diff` (스테이지 + 워킹)
- 관련 `.harness/spec/{...}.md`

## 평가 항목

| # | 항목 | 합격 기준 |
|---|------|----------|
| 1 | 스펙 정렬 | spec 의 모든 성공 기준이 코드로 구현 |
| 2 | 엣지 케이스 | null, empty, 동시성, 실패 경로 처리 |
| 3 | 보안 | 입력 검증, 권한, 시크릿, SQL injection |
| 4 | 경계 검증 | 외부 입력 지점에 validator 가 있는가 |
| 5 | 파일/함수 크기 | 800/50 라인 초과 없음 |
| 6 | 테스트 커버 | 새 로직의 커버리지 ≥ 계약값 |

## 출력

```
## Code Review — {feature}
| 항목 | 판정 | 근거 |
| 1. 스펙 정렬 | PASS | §2 5개 중 5개 구현 |
| 2. 엣지 케이스 | FAIL | empty input 미처리 (file:line) |
...
판정: FAIL
다음 단계: {구체적 수정 요청}
```

## 금지

- "대충 비슷" → FAIL
- 작성 세션과 같은 컨텍스트에서 실행 (별도 서브에이전트 권장)
