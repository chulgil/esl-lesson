#!/usr/bin/env python3
"""Unattended autonomy guard for cg-harness night mode.

PreToolUse 단계에서 야간 무인모드(CG_UNATTENDED=1)일 때만 동작하는 안전 백스톱.
unattended-autonomy.md 룰의 "안전 바닥"을 기계적으로 강제한다.

평상시(CG_UNATTENDED != "1") 에는 즉시 통과 (exit 0) — 대화형 세션에 무영향.

무인모드에서 차단(exit 2 -> Claude 가 도구 호출 차단 + stderr 전달)하는 것:
  * AskUserQuestion          : 질문 금지 -> 자율결정 또는 defer 안내
  * Bash (비가역/외부/시크릿/비용): 명령을 세그먼트로 쪼개 안전바닥 패턴 검사
  * Write/Edit/MultiEdit     : worktree 밖 쓰기 + 가드/게이트 파일 변조 + 시크릿 쓰기 차단
  * mcp__* (외부 송신/쓰기)   : 외부 게시·전송 도구 차단(읽기 전용만 허용)

가드는 보조 방어선이다 — 주 방어선은 격리 worktree(blast radius 한정)와 unattended-autonomy.md 룰.
설계상 한계: 셸 동적 합성·일부 MCP 매처는 100% 막지 못한다. README 의 "잔여 위험" 참조.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# 읽기 전용 뷰어 — 이 명령이 세그먼트의 선두면 CMD 패턴은 데이터로 보고 건너뛴다.
# (단, 시크릿 파일 접근은 뷰어 여부와 무관하게 항상 검사한다.)
READ_ONLY_LEADERS = {
    "grep",
    "rg",
    "egrep",
    "fgrep",
    "cat",
    "bat",
    "less",
    "more",
    "head",
    "tail",
    "echo",
    "printf",
    "ls",
    "tree",
    "wc",
    "awk",
    "sed",
    "jq",
    "column",
    "sort",
    "uniq",
    "comm",
    "diff",
    "file",
    "stat",
    "od",
    "xxd",
    "strings",
    "man",
}

# 시크릿 파일 접근 — 어떤 세그먼트(뷰어 포함)에서든 차단.
SECRET_FILE_PATTERNS: list[tuple[str, str]] = [
    (r"\.env(?!\.example|\.sample|\.template)\b", ".env 시크릿 접근"),
    (r"\bsecrets?\.(json|ya?ml|toml|env)\b", "secrets 파일 접근"),
    (r"\b(id_rsa|id_ed25519)\b", "SSH 개인키 접근"),
    (r"\.pem\b", "인증서/키 접근"),
    (r"\.netrc\b", "자격증명 파일 접근"),
]

# 비뷰어 세그먼트에만 적용하는 위험 명령. git 류는 선택 플래그(-c/-C ...) 뒤 서브커맨드로 정밀 매칭.
_GIT = r"git\s+(?:-[A-Za-z]\S*\s+\S*\s+|--?\S+\s+)*"
CMD_PATTERNS: list[tuple[str, str, str]] = [
    # 비가역
    (rf"\b{_GIT}push\b", "external", "git push — 원격 송신"),
    (rf"\b{_GIT}reset\s+--hard", "irreversible", "git reset --hard"),
    (rf"\b{_GIT}clean\s+-\S*f", "irreversible", "git clean -f"),
    (rf"\b{_GIT}rebase\b", "irreversible", "git rebase — 히스토리 재작성"),
    (rf"\b{_GIT}filter-(branch|repo)", "irreversible", "git filter — 히스토리 재작성"),
    (r"\brm\s+-\S*r", "irreversible", "rm 재귀 삭제"),
    (r"\bdrop\s+(table|database)\b", "irreversible", "DROP TABLE/DATABASE"),
    (r"\btruncate\s+table\b", "irreversible", "TRUNCATE TABLE"),
    (r"\balembic\s+(up|down)grade", "irreversible", "DB 마이그레이션"),
    (r"\bprisma\s+migrate\s+(deploy|reset)", "irreversible", "DB 마이그레이션"),
    (r"\bflyway\b", "irreversible", "DB 마이그레이션"),
    (r"manage\.py\s+migrate", "irreversible", "DB 마이그레이션"),
    # 외부 송신/공개
    (r"\bgh\s+pr\s+(create|merge)", "external", "PR 생성/머지"),
    (r"\bgh\s+release\s+create", "external", "릴리스 발행"),
    (r"\b(npm|pnpm|yarn)\s+publish", "external", "패키지 publish"),
    (r"\buv\s+publish", "external", "패키지 publish"),
    (r"\btwine\s+upload", "external", "패키지 publish"),
    (r"\bcargo\s+publish", "external", "패키지 publish"),
    (r"\bgem\s+push", "external", "패키지 publish"),
    (r"\b(curl|wget)\b", "external", "외부 네트워크 호출 — exfil/과금 위험"),
    (r"\b(ssh|scp|rsync|sftp)\b", "external", "원격 전송"),
    (r"\b(mail|sendmail|msmtp|mutt)\b", "external", "이메일 송신"),
    (r"\bnc\s+-", "external", "netcat — 외부 연결"),
    # 비용/배포
    (r"\b(aws|gcloud|az)\s+\w", "cost", "클라우드 CLI — 과금/배포 위험"),
    (r"\bkubectl\s+\w", "cost", "kubectl — 클러스터 변경 위험"),
    (r"\bterraform\s+(apply|destroy)", "cost", "인프라 변경"),
    (r"\bdocker\s+(push|system\s+prune)", "cost", "docker push/prune"),
    (r"\b(vercel|netlify|firebase|serverless)\s+deploy", "cost", "배포"),
]

# Write/Edit 로 건드리면 안 되는 보호 경로(worktree 내부라도). 가드·게이트 변조(검증 해킹) 차단.
PROTECTED_WRITE = [
    r"/\.claude/settings\.json$",
    r"/\.claude/hooks/",
    r"/\.cg/mechanical\.toml$",
]

# MCP 도구 액션 동사
MCP_SEND = (
    "create",
    "update",
    "delete",
    "send",
    "post",
    "publish",
    "comment",
    "upload",
    "merge",
    "transition",
    "move",
    "edit",
    "set",
    "add",
    "remove",
)
MCP_READ = (
    "get",
    "fetch",
    "search",
    "read",
    "list",
    "query",
    "resolve",
    "describe",
    "download",
    "view",
    "lookup",
)


def _segments(command: str) -> list[str]:
    return [s for s in re.split(r"&&|\|\||[;\n|]", command) if s.strip()]


def _leader(segment: str) -> str:
    for tok in segment.strip().split():
        if "=" in tok and not tok.startswith("-"):  # env VAR=val 접두 건너뜀
            continue
        return tok.split("/")[-1].strip("\"'`(")
    return ""


def _check_bash(command: str) -> tuple[str, str] | None:
    lower = command.lower()
    for seg in _segments(lower):
        for pat, reason in SECRET_FILE_PATTERNS:  # 시크릿: 뷰어 포함 항상
            if re.search(pat, seg):
                return ("secret", reason)
        if _leader(seg) in READ_ONLY_LEADERS:  # 뷰어 선두 -> CMD 는 데이터로 간주
            continue
        for pat, klass, reason in CMD_PATTERNS:
            if re.search(pat, seg):
                return (klass, reason)
    return None


def _check_write(tool_input: dict, project_dir: str) -> tuple[str, str] | None:
    fp = tool_input.get("file_path", "")
    if not fp:
        return None
    try:
        target = Path(fp).expanduser().resolve()
        root = Path(project_dir).resolve()
    except (OSError, RuntimeError):
        return None
    if target != root and root not in target.parents:
        return ("external", f"worktree 밖 쓰기: {fp}")
    s = str(target)
    for pat in PROTECTED_WRITE:
        if re.search(pat, s):
            return ("tamper", f"가드/게이트 파일 수정 금지: {fp}")
    if re.search(r"\.env(?!\.example|\.sample|\.template)\b", s):
        return ("secret", f"시크릿 파일 쓰기: {fp}")
    return None


def _check_mcp(tool: str) -> tuple[str, str] | None:
    action = tool.lower().rsplit("__", 1)[-1]
    if any(v in action for v in MCP_SEND):
        return ("external", f"무인모드 MCP 외부 송신/쓰기 차단: {tool}")
    if any(action.startswith(v) or v in action for v in MCP_READ):
        return None
    return ("external", f"무인모드 MCP 도구 보수적 차단(읽기 미확인): {tool}")


def _emit_queue(project_dir: str, snippet: str, klass: str, reason: str) -> None:
    try:
        status = Path(project_dir) / ".harness" / "status"
        status.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%H:%M")
        line = (
            f"\n## [P1] {stamp} 야간 차단: {reason}\n"
            f"- 막힌 작업: `{snippet[:160]}`\n"
            f"- 차단 사유: 안전 바닥 ({klass})\n"
            f"- 준비된 것: (없음 — 사람이 직접 판단)\n"
            f"- 추천: 아침에 의도 확인 후 수동 실행\n"
        )
        (status / "night-queue.md").open("a", encoding="utf-8").write(line)
    except OSError:
        pass


def _block(
    project_dir: str, snippet: str, klass: str, reason: str, guidance: str
) -> int:
    _emit_queue(project_dir, snippet, klass, reason)
    sys.stderr.write(f"[unattended-guard] 차단({klass}): {reason}. {guidance}\n")
    return 2


def main() -> int:
    if os.environ.get("CG_UNATTENDED") != "1":
        return 0  # 대화형 세션 — 가드 무력

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return 0

    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    defer = (
        "야간 무인모드 안전 바닥 — 자동 실행 불가. .harness/status/night-queue.md 로 "
        "defer 기록함. 다른 독립 작업을 계속하라(로컬 커밋까지만, push 금지)."
    )

    if tool == "AskUserQuestion":
        sys.stderr.write(
            "[unattended-guard] 무인모드: 사용자에게 질문 금지(답이 안 옴). "
            "추천 기본값으로 자율 결정하고 .harness/status/night-decisions.md 에 "
            "[질문/선택/근거/되돌리기/신뢰도]를 기록한 뒤 진행하라. 단 비가역·외부·시크릿·"
            "비용·책임 결정이면 자율결정 금지 — night-queue.md 로 defer 하라.\n"
        )
        return 2

    if tool == "Bash":
        command = tool_input.get("command", "") or ""
        hit = _check_bash(command)
        if hit:
            return _block(project_dir, command, hit[0], hit[1], defer)

    elif tool in ("Write", "Edit", "MultiEdit"):
        hit = _check_write(tool_input, project_dir)
        if hit:
            return _block(
                project_dir, tool_input.get("file_path", ""), hit[0], hit[1], defer
            )

    elif tool.startswith("mcp__"):
        hit = _check_mcp(tool)
        if hit:
            return _block(project_dir, tool, hit[0], hit[1], defer)

    return 0


if __name__ == "__main__":
    sys.exit(main())
