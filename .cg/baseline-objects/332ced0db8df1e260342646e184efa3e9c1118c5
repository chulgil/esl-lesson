#!/usr/bin/env python3
"""PreCompact hook — 컴팩션 직전 working-set 스냅샷.

컴팩션은 컨텍스트를 요약하지만 "지금 무슨 작업 중이었는지"의 SSOT 포인터를
잃을 수 있다. 이 훅은 ``.harness/status/handoff.md`` 에 파일시스템 기반 스냅샷을
남겨 컴팩션 후에도 ``cg-resume`` 가 재개점을 복원하게 한다.

근거: Anthropic "effective harnesses" — 세션 간 context reset 은 컴팩션만으론
부족하므로 외부 파일로 working-set 을 영속화한다.
"""

from __future__ import annotations

import json
import sys
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
    trigger = str(payload.get("trigger", "precompact"))

    root = find_project_root(Path.cwd())
    if root is None:
        return

    out = write_snapshot(root, trigger=f"precompact/{trigger}")
    if out is not None:
        print(
            f"[cg-harness] working-set 스냅샷 저장: {out} — "
            "컨텍스트 손실 시 cg-resume 로 복원.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
