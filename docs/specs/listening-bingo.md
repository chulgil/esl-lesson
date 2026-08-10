# 스펙: 리스닝 빙고 — 원어민 음성/TTS 단어 빙고 (1~4인)

> 작성: 2026-08-10 (구현 동시) · 기획: [proposal/listening-bingo-2026-08.md](../proposal/listening-bingo-2026-08.md)

음성으로 불러주는 단어를 각자 4x4 보드에서 찾아 탭 — 텍스트 문제 없이 **듣고
인지(recognition)** 가 전부인 첫 멀티게임. 속도·타이핑 압박이 없어 초급의 첫
멀티게임을 겨냥한다.

## 규칙

- 인원: 솔로(듣기 기록) / 방 코드 2~4인(방장 시작, 친구 초대 지원)
- 보드: **전원 같은 16단어, 배치만 다름** (플레이어별 시드 셔플)
- 보드 선정 = 기본 단어 풀(내 학습 단어, 3-12자)에서 **due·최근 오답 우선 →
  원어민 구간 보유 우선 → 나머지** (P0-A 우선 출제 규칙 공유, 셔플 후 안정 정렬)
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

## 엣지 케이스

| 케이스 | 처리 |
|--------|------|
| 이탈자 | `done_current` 자동 통과 — 라운드를 막지 않음. 전원 이탈 시 세션 정리 |
| 음성 자동 재생 차단 (브라우저 정책) | "다시 듣기" 버튼 상시 노출 — 수동 재생 |
| 원어민 구간 없는 단어 | TTS 로 재생 (전 단어 보장) — media 는 있으면 병행 |
| 우선 풀 조회 실패 | 빈 셋 폴백 — 게임 시작 보장 (P0-A 와 동일) |
