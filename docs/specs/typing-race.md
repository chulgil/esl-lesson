# 스펙: 영문 타자연습 — 문장 동기 레이스 (1~4인)

> 최종 수정: 2026-07-16 · P1 구현 완료

샘플 문장 하나를 모두가 동시에 타이핑 — **전원이 완성하면 다음 문장**.
문장은 내 학습 풀의 sentence 항목(가시성 규칙 준수)에서 나온다.

## 규칙

- 총 10문장, 문장당 제한 30초 (한 명이 멈춰도 진행 — 미완성은 정타 prefix 만 인정)
- 인원: 솔로(즉시 시작) / 방 코드 2~4인(방장이 시작)
- 화면: 샘플 문장 + **플레이어별 실시간 진행 줄**(정타 prefix 고스트) + 개별 WPM
- 승부: 완성 문장 수 → 정타 수 → 누적 시간 순. 전 기준 동률 = 무승부
- WPM = (정타/5)/분, 정확도 = 정타/(정타+오타)
- 문장 풀 5개 미만이면 `sentences_insufficient` 안내

## 프로토콜 (WS /ws/game, `tp.*`)

| C→S | S→C |
|---|---|
| `tp.solo` / `tp.create` / `tp.join{code}` / `tp.begin`(방장) | `tp.room{code,host,players}` / `tp.start{sentences,total,sentence_seconds,countdown,players}` |
| `tp.typing{idx,chars}` (정타 prefix, 2자 단위 스로틀) | `tp.sentence{idx}` / `tp.typing{name,chars,wpm}` / `tp.done_mark{name,idx,wpm}` |
| `tp.done{idx,chars,errors}` / `tp.leave` | `tp.review{items[]}` (개인) / `tp.end{results,winner,aborted}` |

## 구현 위치

- 서버: `services/game/typing_race.py` (문장별 대기 루프, 이벤트 기반) ·
  저장 `typing_races` (마이그레이션 d0e1f2a3b4c5, mode solo|race)
- 클라: `app/game/typing/page.tsx` — 로비/대기실/레이스(플레이어 줄)/결과

## 오답 → 원탭 학습 (2026-07-16, P2)

오타 완성(`errors>0`)·시간초과 문장을 기록해 정상 종료 시
`tp.review{items:[{item_id,en,ko}]}` 를 본인에게만 전송 (item_id 중복 제거 —
순환 풀 대응, aborted 미전송). 결과 화면 `ReviewPanel`(전 게임 공용 컴포넌트,
규칙은 quiz-royale.md "오답 → 원탭 학습" 과 동일). 문장 카드는 학습 레벨
'고급'에서 출제 — 패널 안내 문구로 고지.

## P2 후보

개인 최고 WPM 기록 표시, 리더보드
