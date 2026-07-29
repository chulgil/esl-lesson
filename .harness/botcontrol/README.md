# 인바운드 Bot control (Telegram · opt-in)

채팅앱에서 **고정 명령**으로 야간 무인 루프를 시작·중지하거나 상태를 조회한다.
ZCode(GLM 하네스)의 "Bot control" 인바운드 절반. `.harness/night/notify.sh`(아웃바운드
알림)의 짝. 실행체는 `.harness/botcontrol/bridge.py`(파이썬 stdlib 만, pip 설치 불필요).

## 왜 최고위험인가 (그리고 왜 그래도 안전한가)

인바운드 = **원격 명령 실행 표면**. 그래서 다층 방어로 막는다:

1. **기본 비활성** — 토큰/허용 chat id 를 환경변수로 주기 전에는 아예 폴링을 시작하지 않는다.
2. **시크릿0 커밋** — 토큰은 `CG_BOTCTL_TG_TOKEN` 환경변수로만. 리포에 절대 넣지 않는다.
3. **발신자 allowlist** — `CG_BOTCTL_ALLOWED_CHAT_IDS` 에 등록된 chat 만 처리. 나머지는 조용히 무시.
4. **고정 verb 디스패치** — 임의 셸/eval 없음. 아래 표의 명령만. 채팅으로 task 텍스트를 넣어
   실행시키는 경로는 없다(작업 지시는 로컬 `.harness/night/task.md` 로만).
5. **강력 verb 이중 게이트** — `/night start` 는 `CG_BOTCTL_ALLOW_NIGHT=1` 일 때만.
6. **안전바닥 상속** — `/night start` 는 기존 `cg-night-run.sh` 를 그대로 띄운다. 격리 worktree,
   push 금지, `unattended-guard.py` 가 그대로 적용된다. 이 브릿지는 **새 권한을 만들지 않는다**.

> 최악의 경우에도 이 브릿지가 할 수 있는 최대치는 "허용된 사용자가, 로컬에 이미 준비된 task 로,
> 격리 worktree 안 야간 루프를 켜고 끄는 것"이다. 임의 셸·외부송신·시크릿 접근은 구조적으로 불가.

## 명령 표

| 명령 | 동작 | 권한 |
|---|---|---|
| `/status` | `cg status` 요약 회신 | 읽기 |
| `/queue` | `night-queue.md`(미결큐) 회신 | 읽기 |
| `/report` | 최신 `night-report-*.md` 요약 회신 (**diff 본문 제외**) | 읽기 |
| `/night start` | 야간 루프 시작(사전 `task.md`+clean tree 필요) | 실행 · 이중 게이트 |
| `/night stop` | `night-stop.flag` 기록 → 러너가 다음 iteration 경계에서 정지 | 쓰기(플래그) |
| `/help` | 도움말 | — |

## 설정 (opt-in)

1. **봇 생성**: Telegram `@BotFather` 로 봇을 만들고 토큰을 받는다.
2. **내 chat id 확인**: 봇에게 아무 메시지나 보낸 뒤
   `https://api.telegram.org/bot<TOKEN>/getUpdates` 의 `message.chat.id` 를 확인.
3. **환경변수**(시크릿은 커밋하지 않는다 — 셸 rc 나 시크릿 매니저로):
   ```bash
   export CG_BOTCTL_TG_TOKEN='123456:AA...'          # BotFather 토큰
   export CG_BOTCTL_ALLOWED_CHAT_IDS='11111111'      # 허용 chat id (콤마구분)
   export CG_BOTCTL_ALLOW_NIGHT=1                     # /night start 허용(생략 시 불허)
   ```
4. **실행**(옵트인 데몬):
   ```bash
   python3 .harness/botcontrol/bridge.py
   ```
   launchd/systemd 로 상시 띄우려면 야간 러너와 같은 방식으로 등록.
5. **셀프테스트**(네트워크 없이 디스패치 표 확인):
   ```bash
   python3 .harness/botcontrol/bridge.py --check
   ```

## 환경변수

| 변수 | 기본 | 의미 |
|---|---|---|
| `CG_BOTCTL_TG_TOKEN` | (없음) | Telegram 봇 토큰. 미설정 시 브릿지 비활성 |
| `CG_BOTCTL_ALLOWED_CHAT_IDS` | (없음) | 허용 chat id, 콤마구분. 미설정 시 비활성 |
| `CG_BOTCTL_ALLOW_NIGHT` | (없음) | `1` 이면 `/night start` 허용 |
| `CG_BOTCTL_POLL_TIMEOUT` | `50` | long-poll 타임아웃(초) |

## 다른 플랫폼 (Slack 등)

Slack 인바운드는 Socket Mode(`slack_sdk` 의존) 또는 slash command(public HTTPS 상시 서버)가
필요해 cg-harness 의 의존성0 원칙과 충돌한다. 따라서 기본 어댑터는 stdlib 로 되는 Telegram 이다.
Slack 을 쓰려면 `dispatch()` 는 그대로 재사용하고 수신·회신부(`poll_loop`/`_send`)만 Slack 어댑터로
교체하면 된다(별도 컴패니언으로 분리 권장 — 코어 보안 로직은 재사용).
