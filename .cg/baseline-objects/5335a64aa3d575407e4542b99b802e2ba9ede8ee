# cg-evaluation — 상세 레퍼런스

> `SKILL.md` 의 요약을 보충하는 상세 문서. 목적/critic 구성/단계 요약은 SKILL.md 참조.

## 왜 3개인가 — Oracle Problem

연구 결과: 같은 AI 가 코드와 테스트를 동시에 쓰면 **테스트는 의도가 아닌 구현을 검증** 하게 됩니다 (정확도 ~6%). 이를 막기 위해:

| Critic | 무엇을 검증 | 독립성 |
|--------|------------|--------|
| Code Critic | spec 정렬, 보안, 엣지 케이스 | 코드 작성자와 분리된 세션 |
| Test Critic | "테스트가 의도를 검증하는가?" | **반드시** 다른 세션. spec 만 읽고 테스트를 재판단. |
| E2E Eval | 실제 실행 시나리오 성공 | 스크립트/Playwright/수동 |

## Stage 1 — Mechanical Verification (필수 선행)

> ouroboros 의 3-Stage Pipeline 패턴 흡수: LLM 호출 이전에 **기계적 검증**
> 으로 명백한 실패를 먼저 걸러낸다. Stage 1 실패 시 Critic 1-3 전체 스킵.

`.cg/mechanical.toml` 의 명령을 순서대로 실행:

| 순서 | 명령 | 실패 시 |
|---|---|---|
| 1 | `build` (예: `uv run python -m compileall -q src/`) | 즉시 중단. 빌드 오류 사용자 보고 |
| 2 | `lint` (예: `uv run ruff check src tests`) | 즉시 중단. 린트 위반 목록 출력 |
| 3 | `test` (예: `uv run pytest tests/ -x -q`) | 즉시 중단. 실패 테스트 요약 |
| 4 | 타임아웃: `timeout = 600` | 시간 초과 = 실패 처리 |

모두 exit 0 → Stage 2 (Critic 1~3) 진행.

**왜 이 순서인가**: LLM 기반 Critic 호출은 시간·토큰 비용이 크다. 린트/빌드/테스트
로 명백한 실패를 먼저 발견하면 LLM 호출을 아낄 수 있고, 피드백 루프도 짧아진다.

출력 예:

```
Stage 1 Mechanical Verification
===============================
build : PASS (exit 0)
lint  : PASS (0 violations)
test  : PASS (12/12)
elapsed: 18s

Stage 2 (LLM Critics) 진행 가능
```

## Critic 1 — Code Critic

**필수 격리**: Agent 도구로 별개 서브에이전트 세션에서 호출. 작성 세션과 같은
컨텍스트에서 "스스로 리뷰" 금지 — 자기확신 편향 발생.

```
Agent(
  description="Code Critic — spec 정렬/보안/경계 검증",
  subagent_type="general-purpose",
  prompt="""
  당신은 Code Critic 입니다. 작성자가 아닙니다.
  아래 스펙과 구현을 읽고 평가하세요.

  입력:
  - spec: .harness/spec/{...}
  - 구현 커밋: {commit-range}

  평가 항목:
  1. 스펙의 모든 성공 기준이 코드로 구현되었는가?
  2. 엣지 케이스 (null, empty, 동시성, 실패 경로) 가 처리되었는가?
  3. 보안 (입력 검증, 권한, 시크릿) 이슈는?
  4. 시스템 경계 (외부 입력) 에서 검증이 있는가?

  FAIL 사유를 구체적으로 기술. PASS 여도 개선 제안 허용.
  결과는 200단어 이내 구조화 포맷. 역할: Verifier.
  """
)
```

## Critic 2 — Test Critic (Oracle Problem 핵심)

**필수 격리**: Agent 도구로 별개 서브에이전트. 코드 파일 Read 금지 도구 제약
필요 (가능하면 `test-critic` 에이전트 정의 사용).

```
Agent(
  description="Test Critic — spec↔test 정렬만, 코드 비열람",
  subagent_type="test-critic",  # .claude/agents/test-critic.md
  prompt="""
  당신은 Test Critic 입니다. 코드는 보지 마세요.

  입력:
  - spec: .harness/spec/{...}
  - 테스트 파일들: {paths}

  평가 항목:
  1. 스펙의 각 성공 기준마다 대응하는 테스트가 있는가?
  2. 테스트가 "의도한 행위" 를 검증하는가, 아니면 "현재 구현"을 복사했는가?
  3. 실패 경로 / 엣지 케이스 테스트가 있는가?
  4. 단위 테스트가 실제로 단위를 격리하는가 (과한 모킹은 오히려 나쁨)?

  테스트가 스펙과 불일치하면 FAIL. 코드를 참조한 흔적이 있으면 FAIL.
  결과는 200단어 이내. 역할: Verifier.
  """
)
```

## Critic 2.5 — Security Reviewer (ultra 모드 필수)

Code Critic 과 **초점을 분리** 한 보안 전담 리뷰. code-review 는 "스펙 충족", security-reviewer 는 "공격자 관점 취약점". 같은 세션이 두 관점을 동시에 유지하기 어려우므로 분리.

```
Agent(
  description="Security Reviewer — 시크릿/injection/권한/암호학",
  subagent_type="security-reviewer",  # .claude/agents/security-reviewer.md
  prompt="""
  당신은 Security Reviewer 입니다. 기능 정합성은 Code Critic 의 일.

  입력:
  - git diff (스테이지 + 워킹)
  - spec: .harness/spec/{...} §5 비기능 요구사항

  평가 항목:
  1. 시크릿 하드코딩 / 입력 검증 / SQL·NoSQL injection
  2. XSS·CSRF / 권한 검증 / 암호학 오용
  3. 에러 메시지 노출 / 의존성 CVE / path traversal / DoS

  CRITICAL 은 즉시 수정 강제. 근거 없이 PASS 금지.
  결과는 200단어 이내. 역할: Verifier.
  """
)
```

적용 기준 (`rules/adaptive-quality.md`):
- **ultra 모드** (security/migration/billing): 필수
- **balanced 모드**: code-review 에서 보안 키워드 발견 시만 호출
- **fast 모드**: 불필요

## Critic 2.7 — 교차 모델 리뷰 (옵션)

Claude 로 작성된 코드를 **다른 모델 가족의 외부 CLI** 가 독립 검증할 수 있다. 같은 모델 가족의 훈련 데이터 편향을 교차 모델로 노출하는 것이 목적.

- 프로젝트에 외부 리뷰 CLI 가 설치되어 있을 때만 사용 (전제 조건은 프로젝트별 CLAUDE.md 에 기록)
- 출력은 `.harness/journal/{date}-crossmodel-review-{feature}.md` 에 저장
- 적용 기준: **ultra 모드** 권장, balanced 선택, fast 불필요

판정 조합:

| Claude | 교차 모델 | 액션 |
|---|---|---|
| PASS | PASS | 진행 |
| PASS | FAIL | 교차 모델 이슈 우선 검토 (모델 편향 노출) |
| FAIL | PASS | Claude 이슈 우선 수정 |
| FAIL | FAIL | Phase 5 복귀, 두 리포트 모두 재시도 프롬프트에 포함 |

## Critic 3 — E2E Eval

| 방식 | 언제 |
|------|------|
| 자동 스크립트 (Playwright, ...) | 반복 가능한 흐름 |
| 에이전트 탐색 E2E (Playwright MCP) | 탐색적 시나리오 |
| 수동 검증 | 자동화 불가 시나리오 |

출력: 시나리오별 PASS/FAIL + 스크린샷 (있으면)

## 종합 판정

| 결과 | 액션 |
|------|------|
| 3개 모두 PASS | Human Checkpoint 로 진행 (아래) |
| 하나라도 FAIL | Phase 5 로 복귀. 실패 컨텍스트를 재시도 프롬프트에 포함. |

## Human Checkpoint — 완료 선언 (필수)

**3-critic 모두 PASS 여도 사람이 명시적으로 "완료"를 선언해야 feature 가 locked
됩니다. 자동 진행 금지.** HSPR 프레임워크의 "누가 이 작업이 끝났다고 말하는가?"
원칙 — 책임·정책 판단은 여전히 사람 영역.

완료 선언 체크리스트:
- [ ] 3-critic 로그를 확인 (evidence 수집)
- [ ] `.harness/spec/{...}.md` §1 의 상태를 `draft` → `locked` 로 변경
- [ ] 마지막 커밋에 trailer 추가: `Closes: .harness/spec/{YYYY-MM-DD}-{slug}.md`
- [ ] Journal 에 `## 완료 선언 — {이름} — {HH:MM}` 엔트리
- [ ] 다음 feature 로 이동하거나 회고

**금지**: critic 모두 PASS 라는 이유로 자동 merge / PR close. 사람의 명시적
"완료" 선언이 없으면 feature 는 `in-review` 상태로 유지.

## Writer ≠ Evaluator — 격리 강제 게이트

> Anthropic 하네스 연구: 같은 세션이 코드를 작성하고 그 코드를 평가하면
> 자기확신 편향(self-confirmation bias)으로 버그 발견율이 60% 이상 떨어진다.
> 이 게이트는 critic 이 "스스로 리뷰" 를 시도하는 패턴을 기계적으로 차단한다.

### 강제 규칙

각 Critic 호출 전에 다음 모든 조건을 확인. 하나라도 위반하면 호출 중단.

| # | 조건 | 검증 방법 |
|---|------|----------|
| 1 | Critic 은 **반드시** Agent 도구로 호출 | 인라인/메인 세션 직접 평가 → 즉시 FAIL |
| 2 | Critic 프롬프트에 "당신은 작성자가 아니다" 명시 | `당신은 {역할}입니다. 작성자가 아닙니다.` 문구 필수 |
| 3 | 입력은 **파일 경로** 로만 전달 (코드 인라인 첨부 금지) | 작성자 컨텍스트 leak 방지 |
| 4 | Test Critic 은 `subagent_type="test-critic"` (도구 제약 적용) | 코드 파일 Read 차단 |
| 5 | 한 세션에서 Critic 2개 이상 동시 호출 금지 | 각 Critic 은 독립 Agent 호출 |
| 6 | Critic 결과는 **인용·요약 후** 메인이 종합 판정 | Critic 결과를 메인이 그대로 통과시키지 않음 |

### 위반 신호와 자동 차단

다음이 감지되면 평가 무효화 + 재실행 강제:

- Critic 결과가 작성 세션의 어휘/주석 스타일을 그대로 반복 (편향 신호)
- Critic 이 "내가 작성한 코드" / "방금 추가한 함수" 같은 1인칭 사용
- Critic 응답이 80% 이상 PASS 인데 mechanical 게이트는 실패 → 형식 PASS 의심

### 권장 호출 패턴

```
# 메인 세션 (작성자)
1. 구현 완료 후 즉시 Stage 1 (mechanical) 실행
2. mechanical PASS → Agent 도구로 Critic 1 호출 (별도 컨텍스트)
3. Critic 1 결과 수신 → 200단어 이내 요약만 컨텍스트 유지
4. Agent 도구로 Critic 2 호출 (또 다른 컨텍스트, test-critic 에이전트)
5. 메인은 두 Critic 의 verdict 만 비교. 코드 재검토 금지.
```

### 적용 모드별

- **ultra 모드**: 1~6 모두 강제. 위반 시 평가 무효.
- **balanced 모드**: 1, 2, 5 강제. 3, 6 권장.
- **fast 모드 / PGE 경량 모드**: Critic 1 만 호출하되 1, 2 는 강제.

## 금지 사항

- **자가 평가 금지**: 코드 작성자가 critic 을 수행하면 원점. 반드시 컨텍스트 분리.
- **PASS 기준 완화 금지**: "대충 비슷" 은 FAIL.
- **Critic 결과 무비판 통과 금지**: Critic 도 틀릴 수 있다. 메인이 종합 판정.
