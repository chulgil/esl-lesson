#!/usr/bin/env python3
"""TaskCompleted journal hook — 완료 task 를 journal 에 1줄 계측 append.

TaskUpdate 완료 명시 또는 팀메이트 완료 시 ``.harness/journal/{YYYY-MM-DD}.md``
에 ``- [HH:MM] task done: {task_subject} ({teammate_name})`` 를 append 한다
(디렉토리 없으면 생성). 야간 러너/멀티에이전트 세션의 진행 계측 피드.

- 계측 전용: exit 는 **항상 0** — TaskCompleted 의 exit 2(완료 반려, stderr 가
  모델 피드백) 시맨틱을 사용하지 않는다. 완료 차단 금지.
- 역할 분리: stop-journal-reminder.py(Stop)는 journal 부재/노후를 *리마인드*만
  하고 쓰지 않는다 — 이 훅은 사실 기록을 *append* 한다. 이벤트도 동작도 달라
  중복 배선이 아니다.
- 어떤 예외에도 non-zero exit 로 세션을 방해하지 않는다. stdlib only.

stdin JSON: {hook_event_name, task_id, task_subject, task_description,
             teammate_name, team_name, session_id, cwd, ...}
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path


def find_project_root() -> Path:
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".harness").is_dir() or (parent / ".cg").is_dir():
            return parent
    return cwd


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        payload = {}

    subject = str(payload.get("task_subject") or payload.get("task_id") or "unknown")
    teammate = str(payload.get("teammate_name") or "")

    journal_dir = find_project_root() / ".harness" / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    today_file = journal_dir / f"{date.today().isoformat()}.md"

    stamp = datetime.now().strftime("%H:%M")
    suffix = f" ({teammate})" if teammate else ""
    with today_file.open("a", encoding="utf-8") as fh:
        fh.write(f"- [{stamp}] task done: {subject}{suffix}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 — 훅은 세션을 방해하지 않는다 (계측 전용)
        pass
    sys.exit(0)
