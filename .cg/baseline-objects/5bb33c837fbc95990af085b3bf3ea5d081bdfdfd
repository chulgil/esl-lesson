---
name: cg-night
description: "사람이 잠든 동안 AI가 무인 자율 Loop 를 돌리는 야간 모드 오케스트레이션. 프리플라이트(의도 선캡처)→격리 worktree→ralph+독립검증→아침 리포트. 트리거: 야간 모드, 자는 동안, 무인 실행, overnight, unattended, cg-night."
---

# cg-night — 자는 동안 도는 Loop

**트리거 키워드**: "자는 동안", "야간", "밤새", "무인", "overnight", "unattended", "cg-night"

## 한 줄 요약

검증 경계 안에서 AI 가 밤새 자율로 일하게 하되, **불확실하면 추측하지 말고 아침 큐로 미루고**, blast radius 를 **격리 worktree 안의 로컬 draft 커밋**으로 묶는다. 정책은 [unattended-autonomy.md](../../rules/unattended-autonomy.md), 기계 강제는 `.claude/hooks/scripts/unattended-guard.py`.

> 하용호 덱: "자고 있을 때 뭔가 진행되고 있지 않다면 아직 덜 간 것." 단, 진행의 대가가 비가역 사고면 안 된다 — 그래서 야간은 "진행"이 아니라 "Defer-not-guess".

## 선행 조건 (없으면 시작 금지)

- [ ] `.harness/spec/{feature}.md` §2 **성공 기준**(검증 경계)이 명문화되어 있다. 없으면 `cg-interview`→`cg-spec-and-harness` 로 먼저 유도.
- [ ] **기계 검증 명령** 존재(`.cg/mechanical.toml` build/test/lint) — Loop 의 합격 판정 근거.
- [ ] `max_iterations`·시간 상한·연속 실패 상한 명시.
- [ ] 깨끗한 git 상태(`git status` clean), 디스크 여유, 토큰 예산.

## 4단계 (사람이 깨어 있을 때 1~2, 잠든 동안 3, 깬 뒤 4)

### 1. 프리플라이트 — 의도 선캡처 (사람이 깨어 있을 때)

야간에 막히지 않으려면 **질문을 미리 다 받아둔다**. `grill-me`/`matt-grill-with-docs` 로 계획의 모호점·가치 트레이드오프를 사람이 자기 전에 해소하고, 답을 `.harness/spec/` + `.harness/knowledge/` 에 영속화한다. (덱: 의도부채는 "AI 가 물어보고 문서화"로 해결.)

> 여기서 받아둔 결정이 많을수록 야간 미결큐가 짧아진다.

### 2. 검증 경계 확정 (사람이 깨어 있을 때)

`rubric-evaluation.md` 의 3종 레이어로 "통과 = 믿을 수 있음" 을 정의:
- **Binary**: 테스트 케이스(최다). **Quantitative**: 시간/처리량. **Qualitative**: LLM-as-judge 루브릭(독립 critic).
- Loop 의 종료 조건 = 이 경계 전부 통과.

### 3. 야간 무인 루프 (잠든 동안 — `CG_UNATTENDED=1`)

격리 worktree 에서 구현→검증 루프를 돌린다(ralph 구성도 설치되어 있다면 `cg-ralph` 루프 규약을 그대로 따른다). 매 iteration:

```
1. 격리: 전용 worktree/브랜치 (main 직접 금지). 산출물은 로컬 draft 커밋만 (push 금지).
2. 구현: 미충족 성공기준만 타겟. 모호한 소프트 결정은 추천기본값으로 진행 + night-decisions.md 기록.
3. 안전바닥 부딪힘: 비가역·외부·시크릿·비용·책임 → 자율결정 금지, night-queue.md 로 defer, 다음 일 계속.
   (unattended-guard.py 가 Bash/AskUserQuestion 을 기계적으로 차단 — 보조 방어선)
4. 독립 검증: cg-evaluation(fresh-context critic) + 기계 게이트 exit code. 테스트 약화 감지 시 폐기.
5. 서킷브레이커: max_iter·시간·연속실패 N회 중 하나 초과 → 즉시 정지 + 사유 기록.
```

### 4. 아침 리포트 (사람이 깬 뒤)

종료 시 `.harness/status/night-report-{YYYY-MM-DD}.md` 생성(러너가 자동 또는 이 스킬이 수동):
1. **diff digest**: 무엇이/왜 + 검증 통과 증거. 2. **결정로그**(night-decisions.md). 3. **미결큐**(night-queue.md, 우선순위순). 4. **다음 액션**: 사람이 승인하면 바로 실행할 push/PR 후보.

> 사람의 첫 작업은 미결큐 처리(가치 결정)와 검증 증거 확인이다 — "초록불만 보고 승인"(인지적 항복) 금지.

## 실행 방법

| 방식 | 명령 | 비고 |
|---|---|---|
| 외부 러너(권장) | `.harness/night/cg-night-run.sh` | bash 루프 + headless `claude -p` + 상한·로그 |
| 스케줄 | `.harness/night/com.cg.night.plist.template` | macOS launchd (취침시각 기동). 수동 설치 |
| 수동 | 이 스킬을 `CG_UNATTENDED=1` 세션에서 호출 | 짧은 작업·드라이런 |

## 종료 처리

| 종료 사유 | 다음 |
|---|---|
| 모든 성공기준 통과 | 아침 리포트 + push/PR 후보 제시(머지는 사람) |
| max_iterations/시간 초과 | 부분 진행을 draft 로 격리 + 미결큐에 잔여 기록 |
| 연속 실패 N회 | 즉시 정지 + (ralph 구성 설치 시) `cg-unstuck` 후보를 미결큐에 |
| 안전바닥 누적 | 모두 미결큐로, 사람 결정 대기 |

## 원칙

- **기본은 멈춤이 아니라 미룸**: 한 항목이 막혀도 다른 독립 작업은 계속(전체 루프는 안 멈춤).
- **검증 해킹 금지**: 작성 세션이 자기 합격 판정 금지. 테스트·어서션·커버리지 약화 금지.
- **blast radius 한정**: 야간 최악 = 격리 worktree 의 로컬 draft. push·머지·배포·외부송신은 구조적으로 불가.
- **max_iterations 필수**: 무한 루프·토큰 폭주 금지.
