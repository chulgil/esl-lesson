# 야간 무인모드 (Night / Unattended)

사람이 잠든 동안 AI 가 검증 경계 안에서 자율 Loop 를 돌린다. 정책 SSOT 는
`.claude/rules/unattended-autonomy.md`, 오케스트레이션은 `.claude/skills/cg-night/`,
기계 강제는 `.claude/hooks/scripts/unattended-guard.py`.

## 30초 요약

```
잠들기 전(사람):  의도 선캡처(grill) → 검증 경계 확정 → .harness/night/task.md 작성
자는 동안(AI):    격리 worktree 에서 ralph 루프 → 막히면 추측 말고 아침 큐로 미룸 → 로컬 draft 커밋
깬 뒤(사람):      night-report 의 미결큐(가치 결정) 처리 + 검증 증거 확인 → push/PR 결정
```

## 안전 모델 (왜 "최대 자율"이 안전한가)

야간 blast radius 를 **격리 worktree 안의 로컬 draft 커밋**으로 묶기 때문이다. 다층 방어:

1. **격리** — 전용 worktree/브랜치. `main` 직접 작업·push 금지. push 자체를 가드가 막는다.
2. **권한** — 러너는 `--permission-mode acceptEdits`(파일편집만 자동승인). 셸은 `.claude/settings.json`
   `permissions.allow` 의 안전·되돌림가능 명령만. (bypassPermissions 를 기본으로 쓰지 않는다.)
3. **가드훅** — `unattended-guard.py` 가 `CG_UNATTENDED=1` 일 때 차단(exit 2)하고 `night-queue.md` 로 defer:
   - **Bash**: 명령을 세그먼트로 쪼개 비가역·외부송신·시크릿·비용 패턴 검사(`git -C dir push`·체이닝 포함, `grep "git push"` 같은 읽기 데이터는 오탐 제외).
   - **Write/Edit/MultiEdit**: worktree 밖 경로·시크릿 파일·**가드/게이트 파일**(`.claude/settings.json`·`.claude/hooks/`·`.cg/mechanical.toml`) 수정 차단(가드 자기무력화·검증해킹 방지).
   - **AskUserQuestion**: 질문 금지 → 자율결정 또는 defer.
   - **mcp__\***: 외부 송신/쓰기 도구 차단, 읽기 전용만 허용.
4. **예산 서킷브레이커** — 반복·시간·연속실패 상한.
5. **독립 검증** — 작성 세션이 자기 합격 판정 금지. `cg diagnose`(기계 게이트)와 `cg-evaluation`
   (fresh-context critic). 테스트·어서션 약화 금지(검증 해킹 차단).

> 그래도 최악의 경우: 격리 브랜치에 쓸 수 없는 draft 가 쌓이는 것까지. push·머지·배포·외부송신·
> 시크릿 접근은 구조적으로 일어나지 않는다.

## 설정

1. **작업 지시서**: `.harness/night/task.md` 에 무인 작업을 적는다(성공 기준 = 검증 경계 명시).
2. **검증 경계**: `.cg/mechanical.toml` 의 build/test/lint 가 합격 판정 근거다. `cg diagnose` 로 확인.
3. **허용 셸**: 야간에 필요한 테스트/빌드 명령을 `.claude/settings.json` `permissions.allow` 에 추가
   (예: `Bash(uv run pytest:*)`). allow 에 없는 셸은 야간에 자동 차단(=defer)된다.
4. **드라이런(필수)**: 처음엔 짧은 작업으로 수동 실행해 검증한다.
   ```bash
   CG_NIGHT_MAX_ITER=2 CG_NIGHT_TIME_BUDGET_MIN=20 ./.harness/night/cg-night-run.sh
   ```
5. **스케줄(선택)**: `com.cg.night.plist.template` 의 `__PROJECT_DIR__` 치환 후 launchd 등록.

### 러너 환경변수

| 변수 | 기본 | 의미 |
|---|---|---|
| `CG_NIGHT_MAX_ITER` | 12 | 최대 반복 |
| `CG_NIGHT_TIME_BUDGET_MIN` | 300 | 벽시계 상한(분) — 세션 5h 한계 고려 |
| `CG_NIGHT_MAX_CONSEC_FAIL` | 3 | 연속 검증 실패 상한 |
| `CG_NIGHT_TASK` | `.harness/night/task.md` | 작업 지시서 |
| `CG_NIGHT_VERIFY` | `cg diagnose` | 합격 판정 게이트(exit 0=통과) |
| `CG_NIGHT_NOTIFY_WEBHOOK` | (없음) | 설정 시 아침 리포트 **요약**을 채팅앱 webhook 으로 push(opt-in). 미설정 시 알림 비활성 |

## 알림 (선택 · opt-in)

자는 동안 돈 결과를 아침에 채팅앱에서 먼저 확인하려면 incoming webhook 을 환경변수로 준다:

```bash
export CG_NIGHT_NOTIFY_WEBHOOK='https://hooks.slack.com/services/...'  # Slack/Discord/Mattermost/Feishu 호환
```

- **기본 비활성**: 미설정이면 알림은 꺼진다. 시크릿은 커밋하지 않는다 — 환경변수로만 준다.
- **요약만 전송**: 프로젝트·날짜·결과·리포트 경로만 보낸다. diff·결정로그·미결큐 **본문은 외부로 보내지 않는다**(유출 방지) — 자세한 내용은 로컬 리포트에서 확인.
- **아웃바운드 전용**: 채팅앱에서 명령으로 야간 루프를 시작·조정하는 **인바운드 원격 제어는 포함하지 않는다**. 시크릿·원격실행 리스크가 커 별도 설계 대상이다.
- **fail-soft**: 알림 전송이 실패해도 야간 루프는 깨지지 않는다. 실행체: `.harness/night/notify.sh`.

## 아침 리포트 읽는 법

`.harness/status/night-report-{날짜}.md`:
1. **미결큐 먼저** — 사람만 결정할 수 있는 가치 트레이드오프·비가역·외부 작업. 여기서 의사결정.
2. **검증 증거 확인** — "결론만 보고 승인"(인지적 항복) 금지. 테스트 통과·게이트 결과를 직접 본다.
3. **결정로그** — AI 가 자율 결정한 것들의 근거·되돌리기. 틀린 전제가 있으면 되돌린다.
4. **push/PR 은 사람이** — 검증 확인 후 `git push -u origin night/...` → PR.

## 잔여 위험 (정직하게)

- **셸 가드 회피**: 가드는 명령 텍스트 정규식 기반이라 동적 합성·우회를 100% 막지 못한다. 1차 방어선은
  격리 worktree(blast radius 한정)와 push 금지다. 더 강한 격리는 컨테이너/네트워크 egress 차단(범위 외).
- **CC 권한/훅 동작은 버전 의존**: `--permission-mode`·PreToolUse exit 2 차단·headless 동작은 CC 버전에
  따라 다를 수 있다. **첫 사용 전 드라이런으로 실제 차단·차단해제를 검증**하라.
- **검증 해킹**: 독립 게이트로 줄이지만 완전 차단은 아니다. irreversible 은 검증 결과와 무관하게 항상
  사람 승인이라는 하드 게이트가 마지막 방어선이다.
