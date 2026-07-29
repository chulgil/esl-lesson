#!/usr/bin/env python3
"""SubagentStop hook — 서브에이전트 완료를 관찰 로그로 적재 + 독립검증 넛지.

두 가지를 한다:
1. ``.harness/status/subagent-log.jsonl`` 에 완료 기록(agent_type·요약·시각)을 append.
   ``cg-trace-analyzer`` 가 반복 실패모드 분석에 쓰는 관찰 피드(harness-signals 패턴).
2. self-report 를 그대로 신뢰하지 말라는 stderr 넛지(verification.md "Agent Delegation").

차단하지 않는다(exit 0). stdlib only.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def find_project_root(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        if (parent / ".harness").is_dir() or (parent / ".cg").is_dir():
            return parent
    return None


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        payload = {}

    root = find_project_root(Path.cwd())
    if root is None:
        return

    agent_type = str(payload.get("agent_type", "unknown"))
    message = str(payload.get("last_assistant_message", ""))
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent_type": agent_type,
        "agent_id": str(payload.get("agent_id", "")),
        "summary": message[:200],
    }

    try:
        status_dir = root / ".harness" / "status"
        status_dir.mkdir(parents=True, exist_ok=True)
        log = status_dir / "subagent-log.jsonl"
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass

    print(
        f"[cg-harness] 서브에이전트({agent_type}) 종료 — self-report 를 그대로 신뢰하지 "
        "말고 git diff·검증 명령 재실행으로 독립 확인(verification.md).",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
