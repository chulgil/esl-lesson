#!/bin/bash
# check-lore-inline.sh - PostToolUse Hook (Edit/Write/MultiEdit)
#
# 스펙/문서의 인라인 **Lore-directive**:/**Lore-constraint**:/**Lore-rejected**:
# 표기를 advisory 경고. 의사결정 기록은 git trailer 1지점 SSOT 정책.
#
# 정책: 의사결정은 커밋 trailer (Lore-directive: / Lore-constraint: / Lore-rejected:)
#   - 신규 스펙 문서에 인라인 표기 금지
#   - 후보 추출: `cg lore propose` (Phase 5 journal 기반)
#
# 감지 시 stderr 경고 + exit 0 (편집은 막지 않음)
#
# 옵트아웃: 위반 라인 위에 또는 파일 상단에
#   `<!-- ignore: lore-inline -->` 주석

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

# 대상: 스펙 문서만
case "$FILE_PATH" in
    */docs/specs/*.md | */.harness/spec/*.md) ;;
    *) exit 0 ;;
esac

[[ ! -f "$FILE_PATH" ]] && exit 0

WARNINGS=$(python3 - "$FILE_PATH" <<'PY'
import re, sys

path = sys.argv[1]
try:
    with open(path, encoding='utf-8') as f:
        content = f.read()
        lines = content.splitlines()
except Exception:
    sys.exit(0)

# 파일 전체 옵트아웃
SILENCE_FILE = re.compile(r'<!--\s*ignore:\s*lore-inline\s*-->', re.MULTILINE)
if SILENCE_FILE.search(content):
    sys.exit(0)

# 인라인 표기 패턴: **Lore-directive**: / **Lore-constraint**: / **Lore-rejected**:
INLINE_RE = re.compile(r'\*\*Lore-(directive|constraint|rejected)\*\*\s*:', re.IGNORECASE)
SILENCE_LINE = re.compile(r'<!--\s*ignore:\s*lore-inline\s*-->')

issues = []
for i, line in enumerate(lines):
    m = INLINE_RE.search(line)
    if not m:
        continue
    above = lines[i - 1] if i > 0 else ''
    if SILENCE_LINE.search(line) or SILENCE_LINE.search(above):
        continue
    issues.append(
        f"{path}:{i+1}: 인라인 **Lore-{m.group(1).lower()}**: 표기 — git trailer 로 이동 권장"
    )

for it in issues:
    print(it)
PY
)

if [[ -n "$WARNINGS" ]]; then
    echo "" >&2
    echo "┌─ Lore 인라인 표기 점검 ─────────────────────────────" >&2
    while IFS= read -r W; do
        [[ -z "$W" ]] && continue
        echo "│ $W" >&2
    done <<< "$WARNINGS"
    echo "│" >&2
    echo "│ 정책: 신규 스펙 인라인 표기 금지 → git trailer 1지점 SSOT" >&2
    echo "│ 작성: 커밋 메시지 마지막 빈 줄 뒤 'Lore-directive: ...' 형식" >&2
    echo "│ 후보 추출: cg lore propose / 조회: git log --grep='^Lore-'" >&2
    echo "│ 옵트아웃: '<!-- ignore: lore-inline -->'" >&2
    echo "└─────────────────────────────────────────────────────" >&2
fi

exit 0
