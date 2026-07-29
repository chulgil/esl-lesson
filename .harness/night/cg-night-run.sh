#!/usr/bin/env bash
#
# cg-night-run.sh — 야간 무인 자율 Loop 러너 (skeleton)
#
# 사람이 잠든 동안 headless `claude -p` 를 격리 worktree 에서 반복 구동한다.
# 안전 모델 (다층 방어):
#   1) 격리 worktree + 로컬 draft 커밋만 (push 금지) -> blast radius 한정
#   2) --permission-mode acceptEdits (파일편집만 자동승인; 셸은 allowlist 만)
#      * bypassPermissions 를 기본으로 쓰지 않는다. 셸은 .claude/settings.json
#        permissions.allow 에 등록된 안전·되돌림가능 명령만 실행된다.
#   3) PreToolUse 가드훅 unattended-guard.py (CG_UNATTENDED=1) 가 비가역·외부·
#      시크릿·비용 명령과 AskUserQuestion 을 기계적으로 차단 -> night-queue.md
#   4) 예산 서킷브레이커: 반복·시간·연속실패 상한
#
# 정책 전문: .claude/rules/unattended-autonomy.md / 스킬: .claude/skills/cg-night/
#
# 사용:
#   CG_NIGHT_TASK=.harness/night/task.md ./.harness/night/cg-night-run.sh
#
set -euo pipefail

# --- 설정 (환경변수로 오버라이드) -------------------------------------------
MAX_ITERATIONS="${CG_NIGHT_MAX_ITER:-12}"
TIME_BUDGET_MIN="${CG_NIGHT_TIME_BUDGET_MIN:-300}"     # 벽시계 상한(분). 세션 5h 한계 고려
MAX_CONSEC_FAIL="${CG_NIGHT_MAX_CONSEC_FAIL:-3}"        # 연속 검증 실패 상한
TASK_FILE="${CG_NIGHT_TASK:-.harness/night/task.md}"   # 무인 작업 지시서 (사람이 미리 작성)
VERIFY_CMD="${CG_NIGHT_VERIFY:-cg diagnose}"            # 합격 판정 게이트 (exit 0 = 통과)

PROJECT_DIR="$(git rev-parse --show-toplevel)"
STAMP="$(date +%Y%m%d-%H%M)"
DAY="$(date +%Y-%m-%d)"
STATUS_DIR="$PROJECT_DIR/.harness/status"
LOG="$STATUS_DIR/night-run-$STAMP.log"
mkdir -p "$STATUS_DIR"
rm -f "$STATUS_DIR/night-stop.flag" 2>/dev/null || true   # 이전 정지 플래그 제거(새 런 오작동 방지)

export CG_UNATTENDED=1
export CLAUDE_PROJECT_DIR="$PROJECT_DIR"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

# --- 프리플라이트 헬스체크 --------------------------------------------------
[ -f "$PROJECT_DIR/$TASK_FILE" ] || { log "ABORT: 작업 지시서 없음 ($TASK_FILE)"; exit 1; }
if [ -n "$(git -C "$PROJECT_DIR" status --porcelain)" ]; then
  log "ABORT: git 워킹트리가 더럽다 — 먼저 정리하라(야간은 깨끗한 상태에서만)"; exit 1
fi
command -v claude >/dev/null || { log "ABORT: claude CLI 없음"; exit 1; }

# --- 격리 worktree ----------------------------------------------------------
BRANCH="night/$STAMP"
WT="$PROJECT_DIR/../$(basename "$PROJECT_DIR")-night-$STAMP"
log "격리 worktree 생성: $WT (브랜치 $BRANCH)"
git -C "$PROJECT_DIR" worktree add -b "$BRANCH" "$WT" >>"$LOG" 2>&1
cd "$WT"
export CLAUDE_PROJECT_DIR="$WT"

# --- Loop -------------------------------------------------------------------
DEADLINE=$(( $(date +%s) + TIME_BUDGET_MIN * 60 ))
CONSEC_FAIL=0
RESULT="incomplete"
PROMPT_PREFIX="너는 야간 무인 자율 세션이다. .claude/rules/unattended-autonomy.md 를 엄격히 따르라. \
불확실하거나 비가역·외부·시크릿·비용·책임 결정이면 추측하지 말고 .harness/status/night-queue.md 로 defer 하고 다른 일을 계속하라. \
자율 결정은 .harness/status/night-decisions.md 에 기록하라. push 금지, 로컬 커밋까지만. 작업 지시:"

# Anthropic long-running harness 흡수: 첫 iteration 은 initializer(부트스트랩) 프롬프트로
# JSON feature-list 를 만들고, 이후 iteration 은 coding 프롬프트로 항목을 하나씩 소화한다.
# JSON 인 이유: markdown 보다 모델의 부적절한 항목 삭제·완화에 강건 (조기완료 방지).
FEATURES_FILE=".harness/night/feature-list.json"
INIT_PROMPT="[부트스트랩] 작업 지시를 검증 가능한 항목들로 전개해 $FEATURES_FILE 에 JSON 배열 \
[{\"id\": \"...\", \"desc\": \"...\", \"passes\": false}] 로 기록하라. 이후 항목 삭제·완화는 금지(추가만 허용). \
기록을 마치면 첫 항목 하나만 구현·테스트·로컬 커밋하라."
CODING_PROMPT="[진행] $FEATURES_FILE 에서 passes:false 인 항목 중 하나만 골라 구현·테스트·로컬 커밋한 뒤 \
그 항목만 passes:true 로 갱신하라(한 iteration 에 한 항목 — one thing per loop). 항목 삭제·완화 금지. \
진행의 정본은 git log 와 feature-list 다."

# 무진전(no-progress) 감지: 실패와 별개로, worktree 상태 스냅샷이 연속으로 변하지 않으면
# 같은 자리를 도는 중 — 예산만 태우기 전에 정지한다 (diff-similarity stall 패턴).
snapshot() {
  { git -C "$WT" rev-parse HEAD 2>/dev/null; \
    git -C "$WT" status --porcelain 2>/dev/null; \
    git -C "$WT" diff HEAD 2>/dev/null; } | git hash-object --stdin
}
NO_PROGRESS=0
MAX_NO_PROGRESS="${CG_NIGHT_MAX_NO_PROGRESS:-2}"
PREV_SNAP="$(snapshot)"

for i in $(seq 1 "$MAX_ITERATIONS"); do
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then log "시간 예산 초과 — 정지"; RESULT="time_budget"; break; fi
  # 외부 정지 요청(botcontrol /night stop): 다음 iteration 경계에서 안전하게 멈춘다.
  if [ -f "$STATUS_DIR/night-stop.flag" ]; then log "외부 정지 요청(night-stop.flag) — 정지"; RESULT="stopped"; rm -f "$STATUS_DIR/night-stop.flag"; break; fi
  log "=== iteration $i/$MAX_ITERATIONS ==="

  # 예산 되먹임: 잔여 예산을 프롬프트에 노출해 하드스톱 전에 스스로 전략을 조절하게 한다.
  REMAIN_MIN=$(( (DEADLINE - $(date +%s)) / 60 ))
  BUDGET_NOTE="[예산] iteration $i/$MAX_ITERATIONS · 남은 시간 약 ${REMAIN_MIN}분. \
예산이 빠듯하면 가장 작은 검증 가능 단위를 우선하고 탐색 깊이를 줄여라."
  if [ -f "$WT/$FEATURES_FILE" ]; then ITER_PROMPT="$CODING_PROMPT"; else ITER_PROMPT="$INIT_PROMPT"; fi

  # headless 실행. acceptEdits = 파일편집 자동승인, 셸은 settings.allow 만. 가드가 안전바닥 차단.
  if ! claude -p "$PROMPT_PREFIX $(cat "$PROJECT_DIR/$TASK_FILE") $BUDGET_NOTE $ITER_PROMPT" \
        --permission-mode acceptEdits >>"$LOG" 2>&1; then
    log "claude -p 비정상 종료 (iteration $i)"
  fi

  # 독립 검증 게이트 (작성 세션과 분리된 프로세스)
  if (cd "$WT" && eval "$VERIFY_CMD") >>"$LOG" 2>&1; then
    log "검증 PASS — 종료"; RESULT="pass"; break
  else
    CONSEC_FAIL=$((CONSEC_FAIL + 1))
    log "검증 FAIL ($CONSEC_FAIL/$MAX_CONSEC_FAIL)"
    [ "$CONSEC_FAIL" -ge "$MAX_CONSEC_FAIL" ] && { log "연속 실패 상한 — 정지"; RESULT="consec_fail"; break; }
  fi

  # 무진전 체크 (실패 카운터와 독립): 스냅샷이 연속 MAX_NO_PROGRESS 회 동일하면 정지.
  CUR_SNAP="$(snapshot)"
  if [ "$CUR_SNAP" = "$PREV_SNAP" ]; then
    NO_PROGRESS=$((NO_PROGRESS + 1))
    log "무진전 ($NO_PROGRESS/$MAX_NO_PROGRESS) — worktree 스냅샷 변화 없음"
    [ "$NO_PROGRESS" -ge "$MAX_NO_PROGRESS" ] && { log "무진전 상한 — 정지"; RESULT="no_progress"; break; }
  else
    NO_PROGRESS=0
  fi
  PREV_SNAP="$CUR_SNAP"
done

# --- 아침 리포트 ------------------------------------------------------------
REPORT="$STATUS_DIR/night-report-$DAY.md"
{
  echo "# 야간 무인 리포트 — $DAY"
  echo ""
  echo "- 결과: **$RESULT** (iterations 사용 $i/$MAX_ITERATIONS)"
  echo "- 격리 worktree: \`$WT\` (브랜치 \`$BRANCH\`, push 안 됨 — 사람 검토 후 결정)"
  echo "- 실행 로그: \`$LOG\`"
  echo ""
  echo "## 변경 요약 (diff digest)"
  echo '```'
  git -C "$WT" --no-pager log --oneline "origin/HEAD..HEAD" 2>/dev/null || git -C "$WT" --no-pager log --oneline -10
  echo '```'
  echo ""
  echo "## 결정로그"
  [ -f "$STATUS_DIR/night-decisions.md" ] && cat "$STATUS_DIR/night-decisions.md" || echo "(없음)"
  echo ""
  echo "## 미결큐 (사람 결정 필요 — 우선순위순)"
  [ -f "$STATUS_DIR/night-queue.md" ] && cat "$STATUS_DIR/night-queue.md" || echo "(없음)"
  echo ""
  echo "## 다음 액션"
  echo "- 미결큐의 가치 결정을 먼저 처리하라(초록불만 보고 승인 금지)."
  echo "- 검증 통과를 확인했으면: \`git -C $WT push -u origin $BRANCH\` 후 PR 생성(사람이)."
} > "$REPORT"

log "아침 리포트: $REPORT"

# --- 아웃바운드 알림 (opt-in: CG_NIGHT_NOTIFY_WEBHOOK 설정 시만) -----------------
# ZCode 흡수: 자는 동안 결과를 채팅앱에서 먼저 확인. 요약만 전송(diff 본문 미전송).
# 인바운드 원격 제어는 미포함 — 시크릿/원격실행 리스크로 별도 설계 대상.
if [ -n "${CG_NIGHT_NOTIFY_WEBHOOK:-}" ]; then
  bash "$PROJECT_DIR/.harness/night/notify.sh" "$REPORT" "$RESULT" >>"$LOG" 2>&1 || true
  log "알림 전송 시도(요약만): CG_NIGHT_NOTIFY_WEBHOOK"
fi

log "끝. 결과=$RESULT"
