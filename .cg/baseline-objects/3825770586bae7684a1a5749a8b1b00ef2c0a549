---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# Unattended Autonomy — 야간 무인 자율운영 결정정책

> 출처: 하용호 "AI시대 나의 전문성을 재설계하는 법"(2026.6) Loop 사상 + 적대적 안전성 검증.
> 목적: 사람이 잠든 동안 AI가 멈추지 않고 일하되, "자동 추측"이 의도부채·비가역 사고로 번지지 않게 한다.
> 활성 조건: 환경변수 `CG_UNATTENDED=1` 일 때만 적용. 평상시(대화형) 세션에는 적용하지 않는다.

## 핵심 반전 — "진행"이 아니라 "Defer-not-guess"

무인모드의 기본 동작은 **멈추지 않고 다 추측해서 진행**이 아니다. 기본은:

> **격리 worktree 안에서 draft 로 일하다, 불확실하거나 고위험이면 그 항목만 멈춰 아침 큐(`night-queue.md`)로 미루고, 독립적인 다른 작업을 계속한다.**

전체 루프는 멈추지 않는다(한 항목이 막혀도 다른 일을 계속). 그러나 위험한 것을 자동 결정하진 않는다. 비유: 야간 당직자는 처리할 수 있는 일은 처리하고, 사장 결재가 필요한 건은 책상에 올려두고 다음 일을 한다 — 사장을 깨우지도, 자기가 사장 도장을 찍지도 않는다.

## 자동결정 정책 (이 프로젝트: "최대 자율")

무인모드에서 명료화가 필요해도 **사용자에게 질문하지 않는다** (`AskUserQuestion` 호출 금지 — 무인이라 답이 안 옴). 대신:

1. **추천 기본값으로 자율 결정**하고 진행한다 — 단, 아래 §안전 바닥에 해당하지 않을 때만.
2. 결정을 `.harness/status/night-decisions.md` 에 **결정로그 포맷**으로 기록한다(의도부채 방지).
3. §안전 바닥에 해당하면 자율 결정하지 말고 `.harness/status/night-queue.md` 로 **defer** 한 뒤 그 항목을 건너뛴다.

> 이 프로젝트는 "최대 자율"을 선택했다 — 모호한 소프트 결정(격리 worktree 내부의 네이밍·파일 배치·구현 방식·되돌릴 수 있는 설계)은 추측해서 진행한다. "최대 자율"이 안전한 유일한 이유는 §안전 바닥이 야간 blast radius 를 **격리 worktree 안의 로컬 draft 커밋**으로 묶기 때문이다.

### 결정로그 포맷 (`night-decisions.md`)

```markdown
## {HH:MM} {한 줄 결정 제목}
- 질문/모호점: {무엇이 불확실했나}
- 선택한 기본값: {무엇을 선택했나}
- 근거: {왜 이게 추천 기본값인가}
- 되돌리기: {어떻게 원복하나 — 커밋 해시/파일}
- 신뢰도: HIGH / MEDIUM / LOW
```

## 안전 바닥 — 자율수준과 무관하게 항상 defer (절대 자동결정 금지)

다음 클래스는 "최대 자율"에서도 **무조건** `night-queue.md` 로 미루고 사람 검토를 기다린다. 기계적 가드(`unattended-guard.py`)가 백스톱으로 강제한다.

| 클래스 | 예 | 이유 |
|---|---|---|
| **비가역(irreversible)** | `rm -rf`, `git reset --hard`, `git push --force`, DB drop/migration, history 재작성 | 복구 불가 |
| **외부 송신/공개** | `git push`(전부), PR 생성/머지, 릴리스/태그, 패키지 publish, 이메일·Slack·Jira·Confluence 게시 | 회수 불가, AI slop 외부 유통 |
| **시크릿/권한** | `.env*`·`secrets.*` read/write, 자격증명 회전, IAM·권한 변경, 토큰 발급 | 유출·권한오용 |
| **비용 큰 작업** | 유료 API 대량 호출, 클라우드 프로비저닝/스케일업, 배포 | 청구 폭탄 |
| **가치 트레이드오프·책임** | 아키텍처 채택, 라이브러리 선택, 스펙 해석 분기, 스코프 변경, 고객·법무·재무 영향 | unknown unknowns — 추천 기본값 전제가 틀려도 AI는 모른다 (하용호 덱 12번: 책임 딸린 결정은 사람이) |

> 분류가 불확실하면 **보수적으로 irreversible 로 간주**해 defer 한다.

### 미결큐 포맷 (`night-queue.md`)

```markdown
## [{우선순위 P0/P1/P2}] {HH:MM} {한 줄 제목}
- 막힌 작업: {무엇을 하려다 멈췄나}
- 차단 사유: {안전바닥 클래스}
- 준비된 것: {사람이 승인하면 바로 실행할 수 있게 준비해 둔 커밋/패치}
- 추천: {사람이 결정할 때 참고할 추천안}
```

## 격리·검증·예산 (필수 안전장치)

- **격리**: 무인 루프는 전용 worktree/브랜치에서만 동작. `main` 직접 커밋·push·merge 금지. 산출물은 **로컬 draft 커밋**으로만 남긴다(push 안 함). → [worktree-parallel-workflow.md](worktree-parallel-workflow.md).
- **독립 검증(검증 해킹 차단)**: 코드를 작성한 세션이 자기 산출물을 합격 판정하지 않는다. 분리된 fresh-context critic(`cg-evaluation`) + 기계 게이트(빌드/테스트/린트 exit code)만 신뢰. **테스트·어서션·커버리지를 약화시키는 변경 금지**(검증 해킹). → [rubric-evaluation.md](rubric-evaluation.md), [verification.md](verification.md).
- **예산 서킷브레이커**: `max_iterations`·토큰 상한·벽시계 시간 상한·연속 실패 N회(기본 3) 중 하나라도 초과하면 즉시 정지하고 아침 큐에 사유를 남긴다. → ralph 구성도 설치되어 있다면 [cg-ralph](../skills/cg-ralph/SKILL.md) 참조.
- **멱등 재개**: 컨텍스트 소진/세션 종료는 부분상태 커밋 금지 — draft 로 격리하고 `cg-resume`+PreCompact/SessionEnd 스냅샷으로 재개. 재개 전 `git status` 정합성 검사.

## 아침 산출물 (사람이 깨어서 가장 먼저 보는 것)

무인 세션 종료 시 `.harness/status/night-report-{YYYY-MM-DD}.md` 를 생성한다:

1. **변경 요약(diff digest)**: 무엇이/왜 바뀌었는지 한 화면 + 검증 통과 증거(테스트 N pass, 게이트 결과). "결론만 보고 승인"(인지적 항복) 방지.
2. **결정로그**: 자율 결정한 모든 항목(`night-decisions.md`).
3. **미결큐**: defer 한 모든 항목(`night-queue.md`) — 우선순위순.
4. **다음 액션**: 사람이 승인하면 바로 실행할 수 있게 준비된 push/PR 후보.

## 금지

- 무인모드에서 `AskUserQuestion` 호출 (답이 안 옴 → 자율결정 또는 defer).
- §안전 바닥 항목을 "추천 기본값"으로 자동 실행.
- 검증을 약화시켜 통과시키기(테스트 삭제·skip·어서션 완화).
- `main` 직접 커밋·push, 또는 worktree 밖으로의 외부 송신.
- 부분 완료 상태를 정식 커밋으로 남기기(draft 격리만).

## 상위 규칙과의 관계

- [worktree-parallel-workflow.md](worktree-parallel-workflow.md): 야간 격리의 전제(전용 worktree, main 보호).
- [verification.md](verification.md) · [rubric-evaluation.md](rubric-evaluation.md): 독립 검증·증거 기반 — 검증 해킹의 방어선.
- [adaptive-quality.md](adaptive-quality.md): 무인 실행은 항상 ultra(보안·비가역 리스크) — 사용자도 하향 불가.
- [goal-fixation-guard.md](goal-fixation-guard.md): defer 는 "이 항목의 산출물은 미결큐 항목"으로 폭주를 끊는다.
- `cg-night` 스킬: 이 정책을 실행하는 야간 루프 오케스트레이션. 기계 강제는 `.claude/hooks/scripts/unattended-guard.py`.
