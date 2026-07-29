#!/bin/bash
# check-version-leftover.sh - PostToolUse Hook (Edit/Write/MultiEdit)
# 스펙 버전 업(vN → vN+1) 후 이전 버전 문자열이 코드에 잔존하면 경고.
#
# 배경: "v6 → v7 설계 전환 후 코드는 v6 구조 잔존" 유형의 드리프트 재발 방지
# (lesson-app 운영에서 흡수한 패턴).
#
# 동작:
#   - 편집한 스펙/코드 파일에서 "v6 → v7" 식 버전 전환 패턴 추출
#   - 이전 버전 문자열이 코드 문자열 리터럴에 남아있으면 stderr 경고 (exit 0 유지)

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    inp = d.get('tool_input', {})
    print(inp.get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# 스펙 md 또는 코드 파일 대상 (old/ 아카이브 제외)
case "$FILE_PATH" in
    *"/specs/old/"* | *"/spec/old/"*) exit 0 ;;
    *"/docs/specs/"*.md | *"/.harness/spec/"*.md) ;;
    *.dart | *.py | *.go | *.java | *.kt | *.ts | *.tsx | *.js) ;;
    *) exit 0 ;;
esac

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
CODE_INCLUDES=(--include="*.dart" --include="*.py" --include="*.go" --include="*.java" --include="*.kt" --include="*.ts" --include="*.tsx" --include="*.js")
EXCLUDES=(--exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=build --exclude-dir=.harness --exclude-dir=docs)

# 파일에서 "v2 → v3", "v6에서 v7" 등 버전 전환 패턴 추출
TRANSITIONS=$(grep -oE "v[0-9]+\s*→\s*v[0-9]+|v[0-9]+에서 v[0-9]+" "$FILE_PATH" 2>/dev/null | head -3)

if [[ -z "$TRANSITIONS" ]]; then
    exit 0
fi

WARNINGS=()

while IFS= read -r TRANS; do
    [[ -z "$TRANS" ]] && continue

    OLD_VER=$(echo "$TRANS" | grep -oE "v[0-9]+" | head -1)
    NEW_VER=$(echo "$TRANS" | grep -oE "v[0-9]+" | tail -1)

    [[ -z "$OLD_VER" || "$OLD_VER" == "$NEW_VER" ]] && continue

    # 코드 문자열 리터럴에서 이전 버전 잔존 여부 확인
    CODE_COUNT=$(grep -rn "${CODE_INCLUDES[@]}" "${EXCLUDES[@]}" -oE "['\"][^'\"]*${OLD_VER}[^'\"]*['\"]" "$REPO_ROOT" 2>/dev/null | wc -l | tr -d ' ')

    if [[ "$CODE_COUNT" -gt 0 ]]; then
        WARNINGS+=("[version-leftover] ${OLD_VER} → ${NEW_VER} 전환 중, 이전 버전 문자열 ${CODE_COUNT}건 코드에 잔존")
    fi
done <<< "$TRANSITIONS"

if [[ ${#WARNINGS[@]} -gt 0 ]]; then
    echo "" >&2
    echo "┌─ 버전 전환 잔재 감지 ─────────────────────────────" >&2
    for W in "${WARNINGS[@]}"; do
        echo "│ $W" >&2
    done
    echo "│ 권장: grep으로 이전 버전 잔재 확인 후 제거" >&2
    echo "└───────────────────────────────────────────────" >&2
fi

exit 0
