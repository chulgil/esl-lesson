#!/usr/bin/env python3
"""Working-set 스냅샷 공유 헬퍼 — handoff 훅(PreCompact·SessionEnd)이 공유.

파일시스템만 읽어 "지금 어디까지 했는지"를 ``.harness/status/handoff.md`` 로 적는다.
transcript 는 읽지 않는다(무겁고 취약) — ``.harness/`` SSOT 포인터만 모은다.
``cg-resume`` 스킬이 이 파일을 복원 시작점으로 쓴다.

stdlib only. 어떤 예외도 세션을 막지 않도록 ``write_snapshot`` 은 실패를 삼키고
None 을 반환한다 (호출 훅은 graceful 종료).
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path


def find_project_root(start: Path) -> Path | None:
    """``.harness`` 또는 ``.cg`` 를 가진 가장 가까운 상위 디렉토리를 반환."""
    for parent in [start, *start.parents]:
        if (parent / ".harness").is_dir() or (parent / ".cg").is_dir():
            return parent
    return None


def _latest(dir_path: Path, pattern: str = "*.md") -> Path | None:
    """패턴에 맞는 파일 중 mtime 이 가장 최근인 것."""
    if not dir_path.is_dir():
        return None
    files = [p for p in dir_path.glob(pattern) if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _tail(path: Path, lines: int = 15) -> str:
    """파일 마지막 N 줄."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    return "\n".join(text.splitlines()[-lines:])


def _git(root: Path, *args: str) -> str:
    """짧은 timeout 의 read-only git 호출. 실패하면 빈 문자열."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def _rel(path: Path | None, root: Path) -> str:
    if path is None:
        return "(none)"
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def build_snapshot(root: Path, *, trigger: str) -> str:
    """파일시스템 기반 working-set 스냅샷 마크다운 본문."""
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    spec = _latest(root / ".harness" / "spec")
    journal = _latest(root / ".harness" / "journal")
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    last_commit = _git(root, "log", "-1", "--format=%h %s")
    dirty = _git(root, "status", "--porcelain")
    dirty_count = len([ln for ln in dirty.splitlines() if ln.strip()])

    lines = [
        "# Handoff Snapshot",
        "",
        f"> 자동 생성 ({trigger}) · {now}",
        "> 컨텍스트가 끊기면 cg-resume 스킬이 이 파일부터 읽어 재개점을 복원합니다.",
        "",
        "## 작업 위치",
        f"- 브랜치: {branch or '(unknown)'}",
        f"- 마지막 커밋: {last_commit or '(none)'}",
        f"- 미커밋 변경: {dirty_count} 파일",
        f"- 활성 spec: {_rel(spec, root)}",
        f"- 최근 journal: {_rel(journal, root)}",
    ]
    if journal is not None:
        lines += ["", "## 최근 journal tail", "```", _tail(journal), "```"]
    return "\n".join(lines) + "\n"


def write_snapshot(root: Path, *, trigger: str) -> Path | None:
    """스냅샷을 ``.harness/status/handoff.md`` 로 저장. 실패는 삼키고 None."""
    try:
        status_dir = root / ".harness" / "status"
        status_dir.mkdir(parents=True, exist_ok=True)
        out = status_dir / "handoff.md"
        out.write_text(build_snapshot(root, trigger=trigger), encoding="utf-8")
        return out
    except OSError:
        return None


__all__ = ["build_snapshot", "find_project_root", "write_snapshot"]
