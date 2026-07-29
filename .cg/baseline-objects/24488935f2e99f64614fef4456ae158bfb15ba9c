#!/usr/bin/env python3
"""Stop journal reminder hook for cg-harness.

세션 종료(Stop) 시 .harness/journal/ 의 오늘 날짜 파일이 있는지 확인하고,
없거나 오래된 경우 stderr 로 갱신 알림을 출력한다.

This also acts as a lightweight PreCompletionChecklistMiddleware: before the
agent exits, it nudges for verification evidence and spec comparison.

Adapted from bkit (Apache-2.0).
"""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path


def main() -> None:
    journal_dir = Path(".harness/journal")
    if not journal_dir.is_dir():
        return

    today_file = journal_dir / f"{date.today().isoformat()}.md"

    if not today_file.exists():
        sys.stderr.write(
            f"[journal-reminder] 오늘의 journal 파일이 없습니다: {today_file}\n"
            "[journal-reminder] 세션 작업 내용을 기록하면 다음 세션에서 컨텍스트가 이어집니다.\n"
            "[pre-completion] Missing verification evidence. Run tests/build/lint and compare against the spec before claiming completion.\n"
        )
        return

    text = today_file.read_text(encoding="utf-8", errors="ignore")
    verification_markers = (
        "verification",
        "검증",
        "pytest",
        "test",
        "PASS",
        "analyze",
        "build",
        "lint",
    )
    if not any(marker in text for marker in verification_markers):
        sys.stderr.write(
            "[pre-completion] No verification evidence found in today's journal. "
            "Record command output and compare against the task spec before exiting.\n"
        )

    mtime = today_file.stat().st_mtime
    age_minutes = (time.time() - mtime) / 60

    if age_minutes > 30:
        sys.stderr.write(
            f"[journal-reminder] journal 이 {int(age_minutes)}분 전에 마지막 갱신되었습니다.\n"
            "[journal-reminder] 세션 종료 전 주요 변경사항을 기록해 두세요.\n"
        )


if __name__ == "__main__":
    main()
