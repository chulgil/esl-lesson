#!/usr/bin/env python3
"""Drift monitor hook for cg-harness.

PostToolUse (Write|Edit) 단계에서 spec/harness 파일을 SHA1 해시로
스냅샷 비교하여 변경을 추적하고, AC Tree 갱신·journal freshness 와
교차 검증해 드리프트 신호를 `.harness/status/drift.json` 에 기록한다.

이 훅은 데이터를 적재만 하고, 사람이 읽는 리포트는 `cg-status` 스킬이
같은 파일을 읽어 생성한다.

Adapted from Q00/ouroboros (MIT).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

SPEC_DIR = ".harness/spec"
HARNESS_DIR = ".harness/harness"
JOURNAL_DIR = ".harness/journal"
STATUS_DIR = ".harness/status"
DRIFT_FILE = "drift.json"
FRESH_SECONDS = 5 * 60


def find_project_root(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        if (parent / ".harness").is_dir() or (parent / ".cg").is_dir():
            return parent
    return None


def hash_markdown_files(dirs: list[Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for base in dirs:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            try:
                data = path.read_bytes()
            except OSError:
                continue
            digest = hashlib.sha1(data).hexdigest()
            rel = str(path.relative_to(base.parent.parent))
            hashes[rel] = digest
    return hashes


def newest_mtime(path: Path) -> float:
    if not path.exists():
        return 0.0
    newest = 0.0
    for item in path.rglob("*"):
        if item.is_file():
            mtime = item.stat().st_mtime
            if mtime > newest:
                newest = mtime
    return newest


def detect_ac_files(spec_dir: Path) -> list[str]:
    if not spec_dir.is_dir():
        return []
    return sorted(p.name for p in spec_dir.glob("ac-tree-*.md"))


def main() -> None:
    root = find_project_root(Path.cwd())
    if root is None:
        print("Success")
        return

    now = time.time()
    spec_dir = root / SPEC_DIR
    harness_dir = root / HARNESS_DIR
    journal_dir = root / JOURNAL_DIR
    status_dir = root / STATUS_DIR
    status_dir.mkdir(parents=True, exist_ok=True)
    drift_path = status_dir / DRIFT_FILE

    current_hashes = hash_markdown_files([spec_dir, harness_dir])
    ac_files = detect_ac_files(spec_dir)

    previous: dict = {}
    if drift_path.is_file():
        try:
            previous = json.loads(drift_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}

    prev_hashes: dict[str, str] = previous.get("hashes", {})
    changed = sorted(
        path
        for path, digest in current_hashes.items()
        if prev_hashes.get(path) != digest
    )
    spec_changed = [p for p in changed if p.startswith(SPEC_DIR + "/")]
    ac_changed = [p for p in spec_changed if Path(p).name.startswith("ac-tree-")]

    journal_mtime = newest_mtime(journal_dir)
    journal_stale = (now - journal_mtime > FRESH_SECONDS) if journal_mtime else True

    spec_changed_without_ac_update = bool(spec_changed) and not ac_changed
    warnings: list[str] = []
    if spec_changed_without_ac_update and ac_files:
        warnings.append(
            "spec_changed_without_ac_update: AC Tree 갱신 없이 spec 만 변경됨"
        )
    if changed and journal_stale:
        warnings.append("journal_stale: 변경이 발생했으나 journal 이 5분 이상 미갱신")
    if spec_changed and not ac_files:
        warnings.append(
            "ac_tree_missing: spec 변경됨에도 ac-tree-*.md 파일이 존재하지 않음"
        )

    summary = {
        "changed_spec_files": len(spec_changed),
        "changed_total_files": len(changed),
        "ac_files_present": len(ac_files),
        "ac_touched": bool(ac_changed),
        "spec_changed_without_ac_update": spec_changed_without_ac_update,
        "journal_stale": journal_stale,
        "warnings": warnings,
    }

    payload = {
        "updated_at": int(now),
        "hashes": current_hashes,
        "ac_files": ac_files,
        "changed": changed,
        "summary": summary,
    }
    drift_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if warnings:
        joined = "; ".join(warnings)
        print(
            f"[cg-harness] 드리프트 신호 감지 — {joined}. "
            "/cg-status 또는 /cg-unstuck 으로 점검 권장."
        )
        return

    print("Success")


if __name__ == "__main__":
    main()
