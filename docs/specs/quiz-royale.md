# 스펙: 스피드 퀴즈 로얄 — 최대 4인 버저 퀴즈

> 최종 수정: 2026-07-16 · P1 구현 완료 · 기획 배경: [proposal/quiz-royale.md](../proposal/quiz-royale.md)

같은 4지선다를 최대 4명에게 동시 출제 — 빠르고 정확할수록 높은 점수.
문제는 대전 소재(내 콘텐츠 선택 규칙 공유)의 단어 풀에서 생성.

## 규칙 (P1 확정)

- 10라운드, 문제당 10초, 1인 1제출(수정 불가)
- 점수: 정답 = `50 + ⌈50 x 남은시간/10⌉` (50~100), 오답/미제출 0
- 라운드 종료(전원 제출 or 시간 만료) → 정답·획득·누적 순위 3초 공개
- 동점은 공동 순위. 진입: 솔로(나+봇 1~3, 즉시 시작) / 방 코드(2~4인, 호스트 시작)
- 봇: 정답률 `0.35+0.1x레벨`, 응답시각 `gauss(7.5-레벨, 1.5)` 클램프
- 단어 풀 최소 15개 미만이면 `words_insufficient` (테트리스와 동일 안내)
- 이탈: 대기실=제거(호스트 이탈 시 방 해체), 진행 중=미제출 계속,
  인간 전원 이탈 시 중단 저장(aborted)

## 프로토콜 (WS /ws/game, `qr.*`)

| C→S | S→C |
|---|---|
| `qr.solo{bot_level,bots,content_ids?}` | `qr.room{code,mode,host,players[]}` |
| `qr.create{content_ids?}` / `qr.join{code}` | `qr.round{no,total,prompt,choices,seconds}` |
| `qr.start` (호스트) / `qr.answer{answer}` | `qr.answered{name}` / `qr.reveal{no,answer,gains,scores}` |
| `qr.leave` | `qr.review{items[]}` (개인) / `qr.end{ranking,aborted}` |

## 구현 위치

- 서버: `services/game/quiz_royale.py` (라운드 루프 = 방당 태스크 1개 +
  0.05s 폴링, 실시간 tick 없음) · 저장 `quiz_royale_matches`
  (마이그레이션 b8c9d0e1f2a3, players JSONB 에 최종 순위)
- 클라: `app/game/QuizRoyale.tsx` (대기실/라운드/공개/시상대),
  로비 `QuizRoyaleEntry` (봇 수 선택 + 방 만들기/입장, 소재 선택 공유)

## 오답 → 원탭 학습 (2026-07-16, P2)

- 라운드마다 오답·미제출 문항 인덱스를 사람 플레이어별로 기록,
  정상 종료 시 `qr.review{items:[{item_id,en,ko}]}` 를 **본인에게만** 전송
  (qr.end 직전, item_id 중복 제거, aborted 매치는 미전송)
- 학습 대상: 의미 모드=출제 단어, 뉘앙스 모드=정답인 '다른 하나' 단어
- 시상대 화면 "이번 판에서 틀린 단어" 패널 — 항목별 [학습 추가] +
  [모두 학습 추가], 기존 `POST /api/cards` 재사용 (이미 덱에 있으면 no-op)
- 휘발성: 결과 화면을 떠나면 사라짐 (저장 없음 — 세션 내 원탭 유도가 목적)

## P2 후보

리더보드 합산, 라운드 수/시간 설정, 관전, 빠른대전 매칭

## 뉘앙스 저격 변형 (2026-07-15)

`variant=nuance` — 임베딩 최근접 2개+앵커(비슷한 뜻 3개)에 먼 단어 1개를 섞어 "뜻이 다른 하나" 저격. 유의어 뉘앙스 훈련. 임베딩 미가용/후보 부족 시 `nuance_unavailable`. 저장·점수·봇은 기본 모드와 동일.
