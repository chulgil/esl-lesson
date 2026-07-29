#!/usr/bin/env python3
"""Per-feature regression eval runner — stdlib only.

Runs every ``*.toml`` in this directory (files starting with ``_`` are
skipped, e.g. ``_template.toml``). Each ``[[case]]`` is a shell command
executed from the project root. A case passes when its exit code matches
``expect_exit`` (default 0) and, when given, ``expect_contains`` is a
substring of stdout.

Exit code: 0 when every case passes, 1 otherwise.
Wired as the opt-in ``eval`` gate in ``.cg/mechanical.toml``
(``cg diagnose --gate eval``). See README.md in this directory.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parents[1]
DEFAULT_TIMEOUT_S = 120


@dataclass(frozen=True)
class CaseResult:
    """Outcome of a single eval case."""

    eval_name: str
    case_name: str
    passed: bool
    detail: str


def _run_case(eval_name: str, index: int, case: dict) -> CaseResult:
    """Execute one [[case]] and compare exit code / stdout expectation."""
    case_name = str(case.get("name", f"case{index}"))
    cmd = case.get("cmd")
    if not isinstance(cmd, str) or not cmd.strip():
        return CaseResult(eval_name, case_name, False, "missing 'cmd'")
    expect_exit = int(case.get("expect_exit", 0))
    expect_contains = case.get("expect_contains")
    timeout_s = int(case.get("timeout", DEFAULT_TIMEOUT_S))
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CaseResult(eval_name, case_name, False, f"timeout after {timeout_s}s")
    if proc.returncode != expect_exit:
        detail = f"exit {proc.returncode} (expected {expect_exit})"
        return CaseResult(eval_name, case_name, False, detail)
    if expect_contains is not None and str(expect_contains) not in proc.stdout:
        detail = f"stdout missing {str(expect_contains)!r}"
        return CaseResult(eval_name, case_name, False, detail)
    return CaseResult(eval_name, case_name, True, "ok")


def _run_eval_file(path: Path) -> list[CaseResult]:
    """Parse one <feature>.toml and run all of its cases."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [CaseResult(path.stem, "-", False, f"invalid toml: {exc}")]
    meta = data.get("eval", {})
    eval_name = (
        str(meta.get("name", path.stem)) if isinstance(meta, dict) else path.stem
    )
    cases = data.get("case", [])
    if not isinstance(cases, list) or not cases:
        return [CaseResult(eval_name, "-", False, "no [[case]] entries")]
    return [_run_case(eval_name, i, case) for i, case in enumerate(cases, start=1)]


def main() -> int:
    """Run all feature evals; print per-case verdicts and a summary line."""
    eval_files = sorted(
        path for path in EVALS_DIR.glob("*.toml") if not path.name.startswith("_")
    )
    if not eval_files:
        print("evals: no eval files found — nothing to run (PASS by default)")
        return 0
    results: list[CaseResult] = []
    for path in eval_files:
        results.extend(_run_eval_file(path))
    for result in results:
        verdict = "PASS" if result.passed else "FAIL"
        print(f"[{verdict}] {result.eval_name} :: {result.case_name} — {result.detail}")
    failed = sum(1 for result in results if not result.passed)
    print(f"evals: {len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
