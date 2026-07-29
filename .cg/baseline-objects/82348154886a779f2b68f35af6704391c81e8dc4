#!/usr/bin/env python3
"""Bash guard hook for cg-harness.

PreToolUse:Bash 단계에서 위험한 명령을 감지하고 경고한다.
파괴적 명령(rm -rf, git reset --hard, DROP TABLE 등)을 stderr 로 경고.
차단하지는 않는다 (exit 0). 경고만.

Adapted from bkit (Apache-2.0).
"""

from __future__ import annotations

import json
import re
import sys

DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-[^\s]*r[^\s]*f", "rm -rf 감지 — 재귀 강제 삭제"),
    (r"\bgit\s+reset\s+--hard", "git reset --hard 감지 — 커밋되지 않은 변경 유실 위험"),
    (r"\bgit\s+push\s+--force", "git push --force 감지 — 원격 히스토리 덮어쓰기 위험"),
    (r"\bgit\s+clean\s+-[^\s]*f", "git clean -f 감지 — 추적되지 않은 파일 삭제"),
    (r"\bdrop\s+table\b", "DROP TABLE 감지 — 데이터 유실 위험"),
    (r"\bdrop\s+database\b", "DROP DATABASE 감지 — 전체 DB 삭제 위험"),
    (r"\btruncate\s+table\b", "TRUNCATE TABLE 감지 — 전체 데이터 삭제"),
    (r"\bkill\s+-9\b", "kill -9 감지 — 프로세스 강제 종료"),
    (r"\bchmod\s+777\b", "chmod 777 감지 — 보안 위험 (전체 쓰기 허용)"),
]


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        data = {}

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        return

    lower = command.lower()
    warnings: list[str] = []

    for pattern, msg in DANGEROUS_PATTERNS:
        if re.search(pattern, lower):
            warnings.append(msg)

    if warnings:
        sys.stderr.write(
            "\n".join(f"[bash-guard] ⚠ {w}" for w in warnings) + "\n"
        )


if __name__ == "__main__":
    main()
