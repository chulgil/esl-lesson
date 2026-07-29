#!/bin/bash
# check-spec-claim.sh - PostToolUse Hook (Edit/Write/MultiEdit)
# 스펙 문서에서 "구현 완료" 체크박스(- [x])를 표시했으나
# 실제 코드에 해당 식별자가 없는 경우 경고.
#
# 배경: "설계 완료 · 코드 0%" 유형의 스펙-코드 괴리 재발 방지
# (lesson-app 운영에서 흡수한 패턴).
#
# 동작 (경량):
#   - 편집 대상이 .harness/spec/*.md 또는 docs/specs/*.md 일 때만 동작
#   - 체크된 줄(- [x])에서 백틱 감싼 식별자(CamelCase, snake_case, 파일명) 추출
#   - 코드 트리 전체에서 grep — 매칭 0건이면 stderr 경고 (exit 0 유지)

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

# 스펙 문서만 대상 (old/ 아카이브 제외)
case "$FILE_PATH" in
    *"/specs/old/"* | *"/spec/old/"*) exit 0 ;;
    *"/docs/specs/"*.md | *"/.harness/spec/"*.md) ;;
    *) exit 0 ;;
esac

REPO_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"

# 코드 확장자 (언어 중립 — 존재하는 것만 grep 에서 매칭됨)
CODE_INCLUDES=(--include="*.dart" --include="*.py" --include="*.go" --include="*.java" --include="*.kt" --include="*.ts" --include="*.tsx" --include="*.js")
EXCLUDES=(--exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=build --exclude-dir=.harness --exclude-dir=docs)

# 체크된 줄에서 백틱으로 감싼 식별자 추출
IDENTIFIERS=$(grep -E "^\s*- \[x\]" "$FILE_PATH" 2>/dev/null \
    | grep -oE '`[A-Za-z_][A-Za-z0-9_]+(\.(dart|py|go|java|kt|ts|tsx|js))?`' \
    | tr -d '`' \
    | sort -u)

if [[ -z "$IDENTIFIERS" ]]; then
    exit 0
fi

WARNINGS=()

while IFS= read -r IDENT; do
    [[ -z "$IDENT" ]] && continue

    # 파일명이면 find, 아니면 심볼 grep
    if [[ "$IDENT" == *.* ]]; then
        FOUND=$(find "$REPO_ROOT" -name "$IDENT" \
            -not -path "*/.git/*" -not -path "*/.venv/*" \
            -not -path "*/node_modules/*" -not -path "*/build/*" \
            2>/dev/null | head -1)
        if [[ -z "$FOUND" ]]; then
            WARNINGS+=("[spec-claim] '완료' 체크된 \`$IDENT\` 파일이 코드 트리에 없음")
        fi
    else
        COUNT=$(grep -rn "${CODE_INCLUDES[@]}" "${EXCLUDES[@]}" -E "\\b${IDENT}\\b" "$REPO_ROOT" 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$COUNT" == "0" ]]; then
            WARNINGS+=("[spec-claim] '완료' 체크된 \`$IDENT\` 심볼이 코드에 없음 — 설계만 완료 가능성")
        fi
    fi
done <<< "$IDENTIFIERS"

if [[ ${#WARNINGS[@]} -gt 0 ]]; then
    echo "" >&2
    echo "┌─ 스펙-코드 괴리 감지 (체크박스 vs 실제 코드) ─────" >&2
    for W in "${WARNINGS[@]}"; do
        echo "│ $W" >&2
    done
    echo "│ 권장: 스펙에서 - [x]로 표시하기 전 실제 코드 확인" >&2
    echo "└───────────────────────────────────────────────" >&2
fi

exit 0
