# 스펙: 리스닝 빙고 — 원어민 음성/TTS 단어 빙고 (1~4인)

> 작성: 2026-08-10 (구현 동시) · 기획: [proposal/listening-bingo-2026-08.md](../proposal/listening-bingo-2026-08.md)

음성으로 불러주는 단어를 각자 4x4 보드에서 찾아 탭 — 텍스트 문제 없이 **듣고
인지(recognition)** 가 전부인 첫 멀티게임. 속도·타이핑 압박이 없어 초급의 첫
멀티게임을 겨냥한다.

## 규칙

- 인원: 솔로(듣기 기록) / 방 코드 2~4인(방장 시작, 친구 초대 지원)
- 보드: **전원 같은 16단어, 배치만 다름** (플레이어별 시드 셔플)
- 보드 선정 = 기본 단어 풀(내 학습 단어, 3-12자)에서 **due·최근 오답 우선 →
  원어민 구간 보유 우선 → 나머지** (공유 원칙: 복습 우선 편입 — P0-A. 셔플 후
  안정 정렬로 16단어 보드 **포함 여부**를 결정)
- **노출 방식(빙고 고유)**: 위 우선순위는 보드 포함(16단어 중 어느 단어가
  뽑히는지)만 결정한다. 실제 호출 순서(`call_order`)는 별도 시드로 다시
  셔플되어 — 우선 항목이 먼저 불리는 게 아니라 16라운드 전반에 고르게
  분산된다 (`pick_board_words`/`_start`, `services/game/bingo.py`)
- 라운드 16회 (호출 소진형, 라운드당 10초 + 정답 공개 1.5초):
  - 클라이언트가 문제 음성 자동 재생 — 신경망 TTS(`speakWord`), 원어민 구간
    (`media`)이 있으면 "원어민 발화로 듣기" 버튼 병행 (SegmentPlayer)
  - 정답 탭: 칸 채움 / 오답 탭: 서버 오답 카운트 + 클라 1초 잠금(난사 방지),
    라운드 안 재시도 허용 / 미탭: 그 칸은 영구 구멍 (재호출 없음)
  - 라운드 끝에 단어+뜻 공개 (받아쓰기 reveal 패턴 — 학습 모먼트)
- 승부: 빙고(가로/세로/대각 1줄) 달성 라운드에서 종료 — 같은 라운드 동시
  빙고는 채운 칸 多 → 오답 少, 전부 동률이면 무승부. 16호출 소진 시 채운 칸
  순위. 속도 보너스 없음 (음성 로드 시간 차가 승부를 가르지 않게)
- 복습 회수: 놓친(미탭) 단어를 `bg.review` 개인 메시지로 → ReviewPanel 원탭
  학습 추가 (전 게임 공통)
- 단어 풀 16개 미만이면 `words_insufficient`

## XP

- 참여 20 XP — `total_xp` 집계에 포함 (2026-08-13 정합 수정 — 다른 5개 게임과
  동일한 참여 규칙, `services/progress.py total_xp`)
- 승리 보너스 없음 — 승리 +30 은 테트리스 전용 산식 (`tetris_wins * 30`), 빙고는
  참여만 인정
- 일일 미션 `game_1`(게임 1판) 카운트에 포함 (`services/retention.py`)
- 주간 명예의 전당(리더보드, `GET /api/game/leaderboards`) 편입은 후속(P2) —
  현재는 테트리스·퀴즈로얄·타자·어순·받아쓰기 5종만 집계

## 프로토콜 (WS /ws/game, `bg.*`)

| C→S | S→C |
|---|---|
| `bg.solo` / `bg.create` / `bg.join{code}` / `bg.begin`(방장) | `bg.room{code,host,players}` / `bg.start{board(내 배치 16),total,round_seconds,countdown,players}` |
| `bg.tap{no,item_id}` (서버 권위 판정) | `bg.round{no,total,media,tts}` / `bg.tap_result{ok,item_id}` / `bg.mark{name,filled}` |
| `bg.leave` | `bg.reveal{no,en,ko,bingo[]}` / `bg.review{items[]}`(개인) / `bg.end{results,winner,aborted}` |

주의: `bg.round.tts` 는 정답 텍스트다 (TTS 재생용) — 네트워크를 열면 답이 보이는
구조는 다른 게임(칩에 정답 노출)과 동일한 신뢰 수준으로 수용.

## 구현 위치

- 서버: `services/game/bingo.py` (BingoManager — typing_race 매니저 구조,
  순수 규칙 `pick_board_words`/`has_bingo`/`BINGO_LINES`) ·
  저장 `bingo_matches` (마이그레이션 9c4e06b9f79e, mode solo|room) ·
  미션 `game_1` 집계 포함 (`services/retention.py`)
- 클라: `app/game/bingo/page.tsx` — 로비/대기실/보드/결과. 게임 허브 카드 등록
- 초대: `invites.GAME_LABELS` "bingo" — 토스트/푸시/알림 센터 공통

## 재대결·히스토리·재접속 (2026-08-20 — 튕김·반복 보고 해소)

| 규칙 | 동작 |
|---|---|
| 방 유지 재대결 | 방 게임 종료 시 방(세션·코드·플레이어) 유지 — 방장 `bg.begin` 으로 재입장 없이 새 매치(새 match 행) 시작. 결과 화면에 "같은 방에서 다시하기"(방장)/대기 안내(게스트). 솔로·크래시 종료는 종전대로 정리 |
| 출제 히스토리 | 사용자별 최근 3판(48단어) 보드 단어 제외 후 선정 (`services/game/history.py ServedHistory` — 인메모리, 서버 재시작 시 초기화. 풀 부족 시 전체 풀 폴백) — 다시하기가 곧 다음 콘텐츠 |
| 재접속 복원 | WS 재접속 시 attach 가 `bg.start` 에 `filled`(내가 채운 칸)·`marks`(전원 진행)를 동봉 — 보드 진행 그대로 복원. 클라이언트 `GameSocket` 은 지수 백오프 자동 재접속 + 백그라운드 복귀 즉시 재연결 (전 게임 공통) |
| 결과 화면 끊김 | completed(재대결 대기) 세션도 진행 중과 같은 detach 경로 — 순간 끊김이 방을 닫지 않고, 전원 이탈 시에만 정리 |
| 오디오 해금 | 첫 탭/클릭(pointerdown)에서 `unlockAudio()` — 서버 트리거 자동 재생(bg.round)이 모바일 자동 재생 정책에 막히던 간헐 무음 해소. TTS 큐 resume(Chrome 백그라운드 고착) 포함 |

## 엣지 케이스

| 케이스 | 처리 |
|--------|------|
| 이탈자 | `done_current` 자동 통과 — 라운드를 막지 않음. 전원 이탈 시 세션 정리 |
| 음성 자동 재생 차단 (브라우저 정책) | "다시 듣기" 버튼 상시 노출 — 수동 재생 |
| 원어민 구간 없는 단어 | TTS 로 재생 (전 단어 보장) — media 는 있으면 병행 |
| 우선 풀 조회 실패 | 빈 셋 폴백 — 게임 시작 보장 (P0-A 와 동일) |
