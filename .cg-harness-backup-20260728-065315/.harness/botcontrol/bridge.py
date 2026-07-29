#!/usr/bin/env python3
"""bridge.py — 인바운드 Bot control 브릿지 (opt-in, stdlib only).

ZCode(GLM 하네스)의 "Bot control" 인바운드 절반. 채팅앱(Telegram)에서 고정 명령으로
cg-night 을 시작·중지하거나 상태를 조회한다. Phase 1(notify.sh)이 아웃바운드였다면,
이건 인바운드 — 그래서 최고위험(원격 명령 실행). 보안 모델은 아래.

보안 모델:
  1) 시크릿0 커밋 — 토큰/허용 chat id 는 환경변수로만. 미설정 시 즉시 종료(기본 비활성).
  2) 발신자 allowlist — CG_BOTCTL_ALLOWED_CHAT_IDS 에 없는 chat 은 조용히 무시.
  3) 고정 verb 디스패치 — 임의 셸/eval 없음. dispatch() 의 고정 표에 있는 명령만.
  4) 강력 verb 이중 게이트 — /night start 는 CG_BOTCTL_ALLOW_NIGHT=1 일 때만.
  5) 안전바닥 상속 — /night start 는 기존 cg-night-run.sh 를 그대로 띄운다
     (격리 worktree·push금지·unattended-guard). 이 브릿지는 새 권한을 만들지 않는다.
  6) task 텍스트 인바운드 금지 — 작업 지시는 로컬 .harness/night/task.md 로만.

의존성: 파이썬 stdlib(urllib/json)만. pip 설치 불필요.

환경변수:
  CG_BOTCTL_TG_TOKEN           Telegram 봇 토큰 (필수; 없으면 비활성)
  CG_BOTCTL_ALLOWED_CHAT_IDS   허용 chat id, 콤마구분 (필수; 없으면 비활성)
  CG_BOTCTL_ALLOW_NIGHT        "1" 이면 /night start 허용 (기본 불허)
  CG_BOTCTL_POLL_TIMEOUT       long-poll 타임아웃 초 (기본 50)

사용:
  CG_BOTCTL_TG_TOKEN=123:abc CG_BOTCTL_ALLOWED_CHAT_IDS=456 \
    python3 .harness/botcontrol/bridge.py

  python3 .harness/botcontrol/bridge.py --check   # 디스패치 표만 출력하고 종료(셀프테스트)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.telegram.org/bot{token}/{method}"
MAX_REPLY = 3500  # Telegram 4096 한계 안쪽 + 요약 원칙

HELP = (
    "cg botcontrol — 사용 가능 명령:\n"
    "/status  현재 하네스 상태 요약\n"
    "/queue   야간 미결큐(사람 결정 필요)\n"
    "/report  최신 야간 리포트 요약(diff 제외)\n"
    "/night start  야간 무인 루프 시작(사전 task.md 필요)\n"
    "/night stop   야간 루프 정지 요청\n"
    "/help    이 도움말"
)


def _project_dir() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except Exception:
        pass
    return Path.cwd()


def _truncate(text: str, limit: int = MAX_REPLY) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…(생략 — 자세한 내용은 로컬에서 확인)"


def _read_file(path: Path, missing: str) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else missing
    except Exception as exc:  # noqa: BLE001 — 브릿지는 절대 죽지 않는다
        return f"(읽기 실패: {exc})"


def _redact_diff(text: str) -> str:
    """리포트에서 diff digest 본문만 제거(유출 방지). 나머지는 유지."""
    out: list[str] = []
    skip = False
    for ln in text.splitlines():
        if ln.startswith("## 변경 요약"):
            out.append("## 변경 요약: (생략 — diff 는 로컬 리포트에서 확인)")
            skip = True
            continue
        if skip and ln.startswith("## "):
            skip = False
        if not skip:
            out.append(ln)
    return "\n".join(out)


def handle_status(project: Path) -> str:
    try:
        out = subprocess.run(
            ["cg", "status"],
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=60,
        )
        body = ((out.stdout or "") + (out.stderr or "")).strip()
        return _truncate("cg status:\n" + body) if body else "상태 정보 없음"
    except FileNotFoundError:
        return "cg CLI 를 찾을 수 없음(PATH 확인)"
    except Exception as exc:  # noqa: BLE001
        return f"status 조회 실패: {exc}"


def handle_queue(project: Path) -> str:
    q = _read_file(project / ".harness" / "status" / "night-queue.md", "미결큐 없음")
    return _truncate("야간 미결큐:\n" + q)


def _latest_report(project: Path) -> Path | None:
    status = project / ".harness" / "status"
    if not status.is_dir():
        return None
    reports = sorted(status.glob("night-report-*.md"))
    return reports[-1] if reports else None


def handle_report(project: Path) -> str:
    rep = _latest_report(project)
    if rep is None:
        return "야간 리포트 없음"
    return _truncate(rep.name + "\n" + _redact_diff(_read_file(rep, "")))


def _start_night(project: Path) -> str:
    runner = project / ".harness" / "night" / "cg-night-run.sh"
    task = project / ".harness" / "night" / "task.md"
    if not runner.is_file():
        return "러너 없음(.harness/night/cg-night-run.sh)"
    if not task.is_file():
        return "작업 지시서 없음(.harness/night/task.md) — 로컬에서 먼저 작성하세요."
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if dirty.stdout.strip():
        return "git 워킹트리가 더럽습니다 — 야간은 clean 상태에서만. 먼저 정리하세요."
    log = project / ".harness" / "status" / "botctl-night.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as fh:
        subprocess.Popen(  # noqa: S603 — 고정 인자, 채팅 입력 미주입
            ["bash", str(runner)],
            cwd=str(project),
            stdout=fh,
            stderr=fh,
            start_new_session=True,
        )
    return "야간 무인 루프 시작됨 — 진행/결과는 아침 리포트와 알림으로 확인하세요."


def handle_night(project: Path, args: list[str]) -> str:
    sub = args[0] if args else ""
    if sub == "stop":
        flag = project / ".harness" / "status" / "night-stop.flag"
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("stop requested via botcontrol\n", encoding="utf-8")
        return "야간 정지 요청됨 — 다음 iteration 경계에서 멈춥니다."
    if sub == "start":
        if os.environ.get("CG_BOTCTL_ALLOW_NIGHT") != "1":
            return "야간 시작은 비활성(CG_BOTCTL_ALLOW_NIGHT=1 필요)."
        return _start_night(project)
    return "사용법: /night start | /night stop"


def dispatch(text: str, project: Path) -> str:
    """고정 verb 디스패치 — 임의 셸/eval 없음."""
    parts = text.strip().split()
    if not parts:
        return ""
    cmd = parts[0].lower()
    args = parts[1:]
    if cmd == "/help":
        return HELP
    if cmd == "/status":
        return handle_status(project)
    if cmd == "/queue":
        return handle_queue(project)
    if cmd == "/report":
        return handle_report(project)
    if cmd == "/night":
        return handle_night(project, args)
    return f"알 수 없는 명령: {cmd}\n{HELP}"


def _api_call(token: str, method: str, params: dict) -> dict:
    url = API.format(token=token, method=method)
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data)  # noqa: S310 — 고정 https 호스트
    with urllib.request.urlopen(req, timeout=70) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _send(token: str, chat_id: str, text: str) -> None:
    try:
        _api_call(token, "sendMessage", {"chat_id": chat_id, "text": text})
    except Exception as exc:  # noqa: BLE001
        print(f"[botctl] sendMessage 실패: {exc}", file=sys.stderr)


def poll_loop(token: str, allowed: set[str], project: Path, timeout: int) -> None:
    offset = 0
    print(
        f"[botctl] 시작 — 허용 chat {sorted(allowed)} · 프로젝트 {project}",
        file=sys.stderr,
    )
    while True:
        try:
            resp = _api_call(
                token, "getUpdates", {"offset": offset, "timeout": timeout}
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[botctl] getUpdates 실패: {exc}", file=sys.stderr)
            time.sleep(5)
            continue
        for upd in resp.get("result", []):
            offset = max(offset, upd.get("update_id", 0) + 1)
            msg = upd.get("message") or upd.get("edited_message") or {}
            chat_id = str((msg.get("chat") or {}).get("id", ""))
            text = msg.get("text", "")
            if not chat_id or chat_id not in allowed:
                continue  # 발신자 allowlist — 조용히 무시
            if not text:
                continue
            reply = dispatch(text, project)
            if reply:
                _send(token, chat_id, reply)


def main(argv: list[str]) -> int:
    if "--check" in argv:
        # 셀프테스트: 고정 디스패치 표만 출력. 네트워크/실행 없음.
        print("botcontrol verbs (fixed allowlist):")
        for verb in (
            "/help",
            "/status",
            "/queue",
            "/report",
            "/night start",
            "/night stop",
        ):
            print(f"  {verb}")
        print("no-arbitrary-shell: True")
        return 0
    token = os.environ.get("CG_BOTCTL_TG_TOKEN", "").strip()
    allowed_raw = os.environ.get("CG_BOTCTL_ALLOWED_CHAT_IDS", "").strip()
    if not token or not allowed_raw:
        print(
            "[botctl] 비활성 — CG_BOTCTL_TG_TOKEN 과 CG_BOTCTL_ALLOWED_CHAT_IDS 를 "
            "설정하면 활성화됩니다(기본 opt-out).",
            file=sys.stderr,
        )
        return 0
    allowed = {c.strip() for c in allowed_raw.split(",") if c.strip()}
    timeout = int(os.environ.get("CG_BOTCTL_POLL_TIMEOUT", "50") or "50")
    poll_loop(token, allowed, _project_dir(), timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
