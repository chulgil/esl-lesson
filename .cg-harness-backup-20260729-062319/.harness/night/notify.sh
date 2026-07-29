#!/usr/bin/env bash
#
# notify.sh — 야간 리포트 요약을 채팅앱으로 아웃바운드 알림 (opt-in)
#
# ZCode(GLM 하네스)의 "Bot control" 에서 흡수한 아웃바운드 절반. 자는 동안 도는
# cg-night 의 결과를 아침에 사람이 채팅앱(Slack/Discord/Mattermost/Feishu 호환
# incoming webhook)에서 먼저 확인하게 한다. 인바운드 원격 제어(채팅앱에서 명령으로
# 야간 루프를 시작·조정)는 포함하지 않는다 — 시크릿·원격실행 리스크가 커 별도 설계 대상.
#
# 안전 모델:
#   1) 시크릿0 커밋 — webhook URL 은 환경변수 CG_NIGHT_NOTIFY_WEBHOOK 로만. 미설정 시 no-op.
#   2) 아웃바운드 전용·요약만 — 리포트의 diff/결정로그/미결큐 본문은 외부로 보내지 않는다
#      (유출 방지). 헤더+결과+리포트 경로 포인터만. 자세한 내용은 로컬 리포트에서 확인.
#   3) fail-soft — 알림 실패가 야간 루프를 깨지 않는다(항상 exit 0).
#
# 사용:
#   CG_NIGHT_NOTIFY_WEBHOOK=https://hooks.slack.com/services/... \
#     ./.harness/night/notify.sh <report-file> <result>
#
set -uo pipefail

WEBHOOK="${CG_NIGHT_NOTIFY_WEBHOOK:-}"
REPORT="${1:-}"
RESULT="${2:-unknown}"

# opt-in: webhook 미설정이면 조용히 종료(기본 비활성). curl 없으면 스킵.
[ -n "$WEBHOOK" ] || exit 0
command -v curl >/dev/null 2>&1 || exit 0

PROJECT="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || echo cg-night)")"
DAY="$(date +%Y-%m-%d 2>/dev/null || echo '')"

# 요약만 — diff/결정 본문은 외부로 보내지 않는다.
SUMMARY="[$PROJECT] 야간 무인 리포트 $DAY — 결과: $RESULT"
if [ -n "$REPORT" ] && [ -f "$REPORT" ]; then
  SUMMARY="$SUMMARY"$'\n'"리포트: $REPORT (미결큐·검증증거는 로컬에서 확인)"
fi

# JSON payload 조립(개행/따옴표 안전 이스케이프). python3 우선, 없으면 한 줄로 폴백.
if command -v python3 >/dev/null 2>&1; then
  PAYLOAD="$(SUMMARY="$SUMMARY" python3 -c 'import json, os; print(json.dumps({"text": os.environ["SUMMARY"]}))')"
else
  ONE_LINE="$(printf '%s' "$SUMMARY" | tr '\n' ' ')"
  PAYLOAD="{\"text\": \"$ONE_LINE\"}"
fi

curl -sS -m 10 -X POST -H 'Content-Type: application/json' \
  --data "$PAYLOAD" "$WEBHOOK" >/dev/null 2>&1 || true

exit 0
