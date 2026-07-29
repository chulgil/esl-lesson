---
description: AI가 구현 계획을 세워줍니다. 확인 후 코딩 시작.
argument-hint: [기능 설명] [--ceo|--eng]
---

# Plan Command

This command invokes the **planner** agent to create a comprehensive implementation plan before writing any code.

## What This Command Does

1. **Restate Requirements** - Clarify what needs to be built
2. **Identify Risks** - Surface potential issues and blockers
3. **Create Step Plan** - Break down implementation into phases
4. **Wait for Confirmation** - MUST receive user approval before proceeding

## 리뷰 모드 (GStack CEO Review 패턴 차용)

`$ARGUMENTS`에서 모드 플래그를 파싱한다:

| 플래그 | 모드 | 관점 | 기본값 |
|--------|------|------|--------|
| `--ceo` | CEO 리뷰 | 제품 비전·사용자 가치·시장 방향 | |
| `--eng` | 엔지니어링 리뷰 | 아키텍처·실행·안정성 | 기본 |

플래그 없으면 `--eng` (기존 동작과 동일).

### `--ceo` 모드 추가 행동

CEO 리뷰 모드가 활성화되면, 기존 planner 에이전트의 기술 분석 **앞에** 다음을 수행한다:

**1. 문제 재정의 — "왜 이걸 만드는가?"**
- 사용자가 제시한 기능을 그대로 받아들이지 않고, 근본 문제를 질문한다
- "이 기능이 해결하려는 사용자의 진짜 고통(pain point)은 무엇인가?"

**2. 텐스타 제품 방향 발굴 (3~5개)**
- 같은 문제를 해결하는 대안적 접근 방향을 제시한다
- 각 방향에 대해: 사용자 임팩트(High/Medium/Low), 구현 복잡도, 차별화 요소를 표로 정리

**3. 범위 모드 선택 요청**

| 모드 | 설명 |
|------|------|
| **10x Vision** | 야심찬 비전. 경쟁사가 없는 영역 탐색 |
| **기본 확장** | 핵심 기능 + 합리적 확장 |
| **Cherry** | 최소 기능만. 범위를 고수 |
| **무자비한 MVP** | 가장 작은 단위로 가치 검증 |

사용자가 범위 모드를 선택하면 해당 범위로 계획을 조정한다.

**4. UX 감정 분석**
- 사용자(최종 사용자)가 이 기능을 사용할 때 느끼는 감정을 예측
- 기쁨/안심/불안/혼란 등의 감정 포인트를 표시

**5. ASCII 아키텍처 다이어그램 필수**
- 시스템 구조를 ASCII 플로우차트로 그려서 사람과 AI 모두 이해하기 쉽게 한다

CEO 리뷰 완료 후, 사용자 확인을 받으면 기존 엔지니어링 계획 단계로 자동 진행한다.

### `--eng` 모드 추가 행동 (기존 + 강화)

기존 planner 에이전트 동작에 다음을 추가한다:

**1. 범위 챌린지** — 수정 예상 파일이 8개 이상이면 범위 축소를 강제로 제안한다:
```
⚠️ 범위 챌린지: [N]개 파일 수정 예상.
더 작은 단위로 나눌 수 있는지 검토합니다.

제안: [축소된 Phase 1만 먼저 구현]
```

**2. ASCII 아키텍처 다이어그램 필수** — 컴포넌트 관계를 ASCII로 표현

**3. "Boring by Default"** — 검증된 기술을 우선 선택. 새로운 기술 도입 시 명확한 근거 제시 필수.

---

## When to Use

Use `/plan` when:
- Starting a new feature
- Making significant architectural changes
- Working on complex refactoring
- Multiple files/components will be affected
- Requirements are unclear or ambiguous
- `--ceo`: 제품 방향성 고민이 필요할 때 (새 기능, 사용자 흐름 재설계)
- `--eng`: 기술적 설계가 복잡할 때 (기본값)

## How It Works

The planner agent will:

1. **Analyze the request** and restate requirements in clear terms
2. **Break down into phases** with specific, actionable steps
3. **Identify dependencies** between components
4. **Assess risks** and potential blockers
5. **Estimate complexity** (High/Medium/Low)
6. **Present the plan** and WAIT for your explicit confirmation

## Example Usage

```
User: /plan I need to add real-time notifications when markets resolve

Agent (planner):
# Implementation Plan: Real-Time Market Resolution Notifications

## Requirements Restatement
- Send notifications to users when markets they're watching resolve
- Support multiple notification channels (in-app, email, webhook)
- Ensure notifications are delivered reliably
- Include market outcome and user's position result

## Implementation Phases

### Phase 1: Database Schema
- Add notifications table with columns: id, user_id, market_id, type, status, created_at
- Add user_notification_preferences table for channel preferences
- Create indexes on user_id and market_id for performance

### Phase 2: Notification Service
- Create notification service in lib/notifications.ts
- Implement notification queue using BullMQ/Redis
- Add retry logic for failed deliveries
- Create notification templates

### Phase 3: Integration Points
- Hook into market resolution logic (when status changes to "resolved")
- Query all users with positions in market
- Enqueue notifications for each user

### Phase 4: Frontend Components
- Create NotificationBell component in header
- Add NotificationList modal
- Implement real-time updates via Supabase subscriptions
- Add notification preferences page

## Dependencies
- Redis (for queue)
- Email service (SendGrid/Resend)
- Supabase real-time subscriptions

## Risks
- HIGH: Email deliverability (SPF/DKIM required)
- MEDIUM: Performance with 1000+ users per market
- MEDIUM: Notification spam if markets resolve frequently
- LOW: Real-time subscription overhead

## Estimated Complexity: MEDIUM
- Backend: 4-6 hours
- Frontend: 3-4 hours
- Testing: 2-3 hours
- Total: 9-13 hours

**WAITING FOR CONFIRMATION**: Proceed with this plan? (yes/no/modify)
```

## Important Notes

**CRITICAL**: The planner agent will **NOT** write any code until you explicitly confirm the plan with "yes" or "proceed" or similar affirmative response.

If you want changes, respond with:
- "modify: [your changes]"
- "different approach: [alternative]"
- "skip phase 2 and do phase 3 first"

## Integration with Other Commands

After planning:
- Use `/tdd` to implement with test-driven development
- Use `/build-and-fix` if build errors occur
- Use `/code-review` to review completed implementation

## Related Agents

This command invokes the `planner` agent located at:
`~/.claude/agents/planner.md`

---

## 후처리: 계획 저장

사용자가 계획을 확인하면, 확정된 계획을 `prompt_plan.md`에 저장한다:
1. 프로젝트 루트의 `prompt_plan.md`에 계획 내용을 기록
2. 기존 `prompt_plan.md`가 있으면 이전 내용을 "## 이전 계획" 섹션으로 아카이브 후 덮어쓰기
3. 저장 후 안내: "계획이 prompt_plan.md에 저장되었습니다."

이렇게 하면 다음 세션에서 `/sync`로 계획을 불러올 수 있다.

## 사용 예시

```bash
# 기존 엔지니어링 계획 (기본값)
/plan 레슨 예약 기능 추가

# CEO 리뷰 모드 — 제품 방향성 먼저 탐색
/plan --ceo 학부모 대시보드 기능

# 엔지니어링 모드 명시 (기본값과 동일)
/plan --eng 결제 시스템 리팩토링
```

## 다음 단계

| 계획이 확정되면 | 커맨드 |
|:---------------|:-------|
| 테스트하면서 구현 | `/tdd` |
| 한 번에 자동 실행 | `/auto` |
| 문서 동기화 | `/sync` (다른 세션에서 이어서 작업 시) |
