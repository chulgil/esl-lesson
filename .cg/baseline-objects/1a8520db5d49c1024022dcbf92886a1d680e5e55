#!/usr/bin/env python3
"""SessionEnd hook — 세션 종료 시 working-set 스냅샷 + journal 점검.

세션이 끝나면 다음 세션은 빈 컨텍스트로 시작한다. 종료 직전 handoff.md 를
갱신해 다음 세션의 ``cg-resume`` 가 즉시 재개점을 잡게 한다. 오늘 journal 이
없으면 경고도 남긴다(stop-journal-reminder 와 같은 정신, 종료 경로).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from _snapshot import find_project_root, write_snapshot
except ImportError:
    sys.exit(0)


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        payload = {}
    reason = str(payload.get("reason", "other"))

    root = find_project_root(Path.cwd())
    if root is None:
        return

    write_snapshot(root, trigger=f"session-end/{reason}")

    journal = root / ".harness" / "journal" / f"{date.today().isoformat()}.md"
    if not journal.exists():
        print(
            "[cg-harness] 세션 종료 — 오늘 journal 이 없습니다. 다음 세션 연속성을 "
            "위해 주요 변경/결정을 .harness/journal 에 남기세요.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
