#!/usr/bin/env python3
"""UserPromptSubmit hook — 학습 신호(거절/교정/승인)를 관찰 로그로 적재.

사용자 프롬프트에서 rejection / correction / confirmation 신호를 키워드 휴리스틱으로
감지해 ``.harness/signals/observations.jsonl`` 에 append 한다. 이 로그는
``cg instinct harvest`` 가 confidence 부착 instinct 로 누적하고, 임계(0.7) 도달분만
``cg absorb propose --from instincts`` 로 승격 후보가 된다 — 세션 내 즉석 승격 금지
(cross-session 누적 + 휴먼게이트, rules/learning-loop.md).

순수 관찰자: stdout 에 아무것도 쓰지 않는다(프롬프트 불변). 어떤 실패도 세션을 깨지
않도록 fail-soft(항상 exit 0). stdlib only. 스니펫은 시크릿 레닥션 후 200자 캡.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# (신호 타입, 트리거 키워드들). 위에서부터 우선순위 — 첫 매칭 타입으로 분류.
SIGNAL_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "rejection",
        (
            "그게 아니",
            "아니라",
            "아니 ",
            "하지마",
            "하지 마",
            "쓰지 마",
            "쓰지마",
            "말고 ",
            "틀렸",
            "잘못됐",
            "잘못했",
            "되돌려",
            "롤백",
            "revert",
            "그만해",
        ),
    ),
    (
        "correction",
        (
            "다시 해",
            "다시해",
            "라니까",
            "왜 안 ",
            "왜 안돼",
            "왜 안 돼",
            "고쳐줘",
            "고쳐라",
            "수정해",
            "말했잖아",
            "다르게 해",
        ),
    ),
    (
        "confirmation",
        (
            "좋아",
            "맞아",
            "완벽",
            "승인",
            "그렇게 진행",
            "진행해",
            "lgtm",
            "approve",
        ),
    ),
)

SNIPPET_CAP = 200

# 시크릿 레닥션 — cg_harness/redact.py 와 동일 패턴 (훅은 stdlib 독립 실행이라 인라인).
_MASK = "[REDACTED]"
_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(
        r"\beyJ[A-Za-z0-9_-]{8,512}\.[A-Za-z0-9_-]{8,512}\.[A-Za-z0-9_-]{8,512}\b"
    ),
)
_KV = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key)\b(\s*[:=]\s*)([^\s,;]+)"
)
_URL_CRED = re.compile(r"\b([a-z][a-z0-9+.-]*://)([^:/\s]+):([^@/\s]+)@")


def redact(text: str) -> str:
    out = _KV.sub(lambda m: f"{m.group(1)}{m.group(2)}{_MASK}", text)
    out = _URL_CRED.sub(lambda m: f"{m.group(1)}{m.group(2)}:{_MASK}@", out)
    for pattern in _TOKEN_PATTERNS:
        out = pattern.sub(_MASK, out)
    return out


def classify(prompt: str) -> tuple[str, str] | None:
    """(신호 타입, 매칭 키워드) — 신호가 아니면 None (기록하지 않음)."""
    lowered = prompt.lower()
    for signal_type, triggers in SIGNAL_MAP:
        for trigger in triggers:
            if trigger in lowered:
                return signal_type, trigger
    return None


def extract_prompt(raw: str) -> str:
    """UserPromptSubmit JSON payload 의 prompt 필드, 아니면 원문 그대로 (구형 호환)."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw
    if isinstance(payload, dict) and isinstance(payload.get("prompt"), str):
        return payload["prompt"]
    return raw


def find_project_root() -> Path | None:
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    candidates = [Path(env_root)] if env_root else []
    candidates.append(Path.cwd())
    for start in candidates:
        for parent in [start, *start.parents]:
            if (parent / ".harness").is_dir():
                return parent
    return None


def main() -> None:
    try:
        raw = sys.stdin.read()
    except OSError:
        return

    prompt = extract_prompt(raw).strip()
    if not prompt:
        return

    matched = classify(prompt)
    if matched is None:
        return

    root = find_project_root()
    if root is None:
        return

    signal_type, trigger = matched
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": signal_type,
        "matched": trigger,
        "snippet": redact(prompt)[:SNIPPET_CAP],
        "source": "user-prompt",
    }

    try:
        signals_dir = root / ".harness" / "signals"
        signals_dir.mkdir(parents=True, exist_ok=True)
        log = signals_dir / "observations.jsonl"
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 — fail-soft: 훅 실패가 세션을 깨지 않게.
        pass
