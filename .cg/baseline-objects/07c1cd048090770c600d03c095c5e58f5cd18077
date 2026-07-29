#!/usr/bin/env python3
"""Notification relay hook — 무인 세션의 주의 필요 알림을 아웃바운드로 중계.

Claude Code 가 알림(Notification 이벤트)을 송출할 때, 사람이 자리에 없는
무인모드(CG_UNATTENDED=1)에서만 ``.harness/night/notify.sh`` 를 호출해
채팅앱 webhook 으로 relay 한다 (야간 러너 계측 강화).

- 대화형 세션(CG_UNATTENDED != "1")은 no-op — 사용자가 터미널에서 알림을 직접
  보므로, night 모듈 전용 아웃바운드 채널(notify.sh)로 중계하면 소음이다.
  (night/README §알림: notify.sh 는 야간 무인 결과를 아침에 확인하는 opt-in 채널)
- night 모듈은 로드아웃 옵션이라 notify.sh 가 프루닝될 수 있다 — 없으면 조용히
  exit 0 (존재 가드). notify.sh 자체도 webhook 미설정이면 no-op (이중 opt-in).
- Notification 은 block 불가(side effect 전용). 어떤 예외에도 non-zero exit 로
  세션을 방해하지 않는다. stdlib only.

stdin JSON: {hook_event_name, message, title, notification_type, session_id, cwd, ...}
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# 사람 주의가 필요한 알림 유형만 relay (settings.json matcher 와 동일 집합 —
# matcher 없이 배선돼도 동작이 같도록 방어적으로 재검사한다).
RELAY_TYPES = frozenset(
    {
        "permission_prompt",
        "idle_prompt",
        "agent_needs_input",
        "agent_completed",
    }
)


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
    if os.environ.get("CG_UNATTENDED") != "1":
        return

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        payload = {}

    notification_type = str(payload.get("notification_type", ""))
    if notification_type not in RELAY_TYPES:
        return

    notify = find_project_root() / ".harness" / "night" / "notify.sh"
    if not notify.is_file():
        return  # night 모듈 프루닝됨 — opt-in 부재는 무해 통과

    title = str(payload.get("title") or "Claude Code")
    message = str(payload.get("message") or notification_type)
    subprocess.run(
        ["bash", str(notify), title, message],
        capture_output=True,
        timeout=8,
        check=False,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 — 훅은 세션을 방해하지 않는다 (fail-soft)
        pass
    sys.exit(0)
