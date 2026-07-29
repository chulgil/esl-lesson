#!/usr/bin/env python3
"""Session Start hook for cg-harness.

하네스 상태를 읽어 세션 시작 시 간단한 컨텍스트 배너를 stderr 로 출력한다.
성공 경로는 stdout 를 비워 Claude 컨텍스트 오염을 피한다.

Also injects compact Directory Context and Tooling context, mirroring the
LocalContextMiddleware pattern from LangChain harness engineering.

Adapted from Q00/ouroboros (MIT).
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

INSTINCT_REMINDER_FLOOR = 0.7
INSTINCT_DECAY_PER_WEEK = 0.02
INSTINCT_MAX_REMINDERS = 3


def find_project_root(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        if (parent / ".harness").is_dir() or (parent / ".cg").is_dir():
            return parent
    return None


def read_current(root: Path) -> str | None:
    candidate = root / ".harness" / "status" / "current.md"
    if not candidate.is_file():
        return None
    try:
        text = candidate.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def discover_context(root: Path) -> list[str]:
    """Return a compact Directory Context / tooling summary."""
    dirs = []
    for name in (".harness", ".cg", "docs", "src", "lib", "test", "tests"):
        if (root / name).exists():
            dirs.append(name)

    tools = []
    for tool in ("git", "python3", "uv", "node", "npm", "flutter", "go", "java"):
        if shutil.which(tool):
            tools.append(tool)

    mechanical = root / ".cg" / "mechanical.toml"
    lines = [
        "[cg-harness] Directory Context:",
        f"- cwd: {root}",
        f"- dirs: {', '.join(dirs) if dirs else '(none detected)'}",
        f"- tools: {', '.join(tools) if tools else '(none detected)'}",
        f"- mechanical.toml: {'present' if mechanical.is_file() else 'missing'}",
    ]
    return lines


def _instinct_meta(text: str) -> dict[str, str]:
    """Parse minimal ``key: value`` frontmatter from an instinct file."""
    meta: dict[str, str] = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return meta
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return meta


def _instinct_pattern(text: str) -> str:
    """First content line of the observed-pattern section."""
    lines = text.splitlines()
    try:
        start = lines.index("## 관찰된 패턴") + 1
    except ValueError:
        return ""
    for line in lines[start:]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def _effective_confidence(meta: dict[str, str], now: datetime) -> float:
    """Stored confidence minus weekly decay (0.02/week). May raise ValueError."""
    confidence = float(meta.get("confidence", "0"))
    try:
        last_seen = datetime.fromisoformat(meta.get("last_seen", ""))
    except ValueError:
        return confidence
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    weeks = max(0, (now - last_seen).days // 7)
    return max(0.0, confidence - INSTINCT_DECAY_PER_WEEK * weeks)


def instinct_reminders(root: Path) -> list[str]:
    """Push-style recall: cue-less (global) high-confidence instincts only.

    Instincts with cues are recalled contextually via
    ``cg instinct list --cue`` instead — no always-on injection.
    """
    directory = root / ".harness" / "instincts"
    if not directory.is_dir():
        return []
    now = datetime.now(timezone.utc)
    scored: list[tuple[float, str]] = []
    for path in sorted(directory.glob("instinct-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            meta = _instinct_meta(text)
            effective = _effective_confidence(meta, now)
        except (OSError, ValueError):
            continue
        if meta.get("status", "active") != "active" or meta.get("cues", ""):
            continue
        pattern = _instinct_pattern(text)
        if effective >= INSTINCT_REMINDER_FLOOR and pattern:
            scored.append((effective, pattern))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        f"- ({effective:.2f}) {pattern}"
        for effective, pattern in scored[:INSTINCT_MAX_REMINDERS]
    ]


def main() -> None:
    root = find_project_root(Path.cwd())
    if root is None:
        return

    for line in discover_context(root):
        print(line, file=sys.stderr)

    try:
        reminders = instinct_reminders(root)
    except Exception:  # hook must never break session start
        reminders = []
    if reminders:
        print("[cg-harness] instinct reminders (confidence >= 0.7):", file=sys.stderr)
        for line in reminders:
            print(line, file=sys.stderr)

    current = read_current(root)
    if current is None:
        return

    head = "\n".join(current.splitlines()[:10])
    print("[cg-harness] .harness/status/current.md:", file=sys.stderr)
    print(head, file=sys.stderr)


if __name__ == "__main__":
    main()
