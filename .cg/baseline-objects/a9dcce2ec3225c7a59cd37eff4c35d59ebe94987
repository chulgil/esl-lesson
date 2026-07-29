#!/usr/bin/env python3
"""LoopDetectionMiddleware for cg-harness.

Tracks repeated edits to the same file and warns the agent to step back instead
of making small variations to the same broken approach.

v2 (loop engineering 흡수): 내용 해시 기반 **진동(oscillation) 감지** 추가 —
파일이 이전 상태로 되돌아가는 A→B→A 플립플롭은 "같은 두 접근 사이를 오가는 중"
이라는 신호다. 반복 횟수 경고(양적)와 별개로 질적 신호를 잡는다.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

STATUS_DIR = Path(".harness/status")
LOOP_FILE = STATUS_DIR / "loop-detection.json"
THRESHOLD = 4
WINDOW_SECONDS = 20 * 60
HASH_HISTORY_CAP = 6  # 파일당 최근 내용 해시 보관 수 (진동 감지 창)


def _extract_path(payload: dict[str, Any]) -> str | None:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("file_path", "path"):
            value = tool_input.get(key)
            if isinstance(value, str) and value:
                return value

    for key in ("file_path", "path"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _load() -> dict[str, Any]:
    if not LOOP_FILE.is_file():
        return {"files": {}}
    try:
        data = json.loads(LOOP_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"files": {}}
    if not isinstance(data, dict):
        return {"files": {}}
    files = data.get("files")
    if not isinstance(files, dict):
        data["files"] = {}
    return data


def _content_hash(path: str) -> str | None:
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:12]
    except OSError:
        return None


def _detect_oscillation(entry: dict[str, Any], current_hash: str) -> bool:
    """직전이 아닌 과거 해시로의 회귀(A→B→A)만 진동으로 판정.

    직전과 동일(A→A, no-op 재기록)은 진동이 아니므로 이력 갱신도 경고도 없다.
    """
    hashes = entry.get("hashes")
    if not isinstance(hashes, list):
        hashes = []
    if hashes and hashes[-1] == current_hash:
        entry["hashes"] = hashes
        return False
    oscillated = current_hash in hashes[:-1] if len(hashes) >= 2 else False
    hashes.append(current_hash)
    entry["hashes"] = hashes[-HASH_HISTORY_CAP:]
    return oscillated


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    path = _extract_path(payload)
    if not path:
        print("Success")
        return

    now = int(time.time())
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    state = _load()
    files: dict[str, Any] = state["files"]
    entry = files.get(path)
    if not isinstance(entry, dict):
        entry = {"count": 0, "first_seen": now, "last_seen": now}

    if now - int(entry.get("first_seen", now)) > WINDOW_SECONDS:
        entry = {"count": 0, "first_seen": now, "last_seen": now}

    entry["count"] = int(entry.get("count", 0)) + 1
    entry["last_seen"] = now

    current_hash = _content_hash(path)
    oscillated = (
        _detect_oscillation(entry, current_hash) if current_hash is not None else False
    )

    files[path] = entry
    state["updated_at"] = now
    LOOP_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if oscillated:
        print(
            "[cg-harness] LoopDetectionMiddleware: 진동(oscillation) 감지 — "
            f"{path} 가 이전 상태로 되돌아갔다(A→B→A). 두 접근 사이를 오가는 중이라는 "
            "신호다. 같은 재시도 대신 에스컬레이션 사다리를 밟아라: 접근 전환(/cg-unstuck) "
            "→ scope 축소 → 사용자에게 트레이드오프 질문."
        )
        return

    if int(entry["count"]) >= THRESHOLD:
        print(
            "[cg-harness] LoopDetectionMiddleware: repeated edits detected for "
            f"{path} ({entry['count']} times). consider reconsidering your approach, "
            "re-read the spec, or use /cg-unstuck."
        )
        return

    print("Success")


if __name__ == "__main__":
    main()
