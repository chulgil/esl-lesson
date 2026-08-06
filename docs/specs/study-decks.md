# 스펙: 학습 덱 — 담은 콘텐츠 단위 학습

> 최종 검증: 2026-07-30 (코드 대조 완료)

Anki 의 "덱별 학습 계획"을 담기(구독) 구조 위에 얹는다. **덱 = 내가 담은 콘텐츠 1개**.
별도 덱 테이블은 만들지 않는다 — `content_subscriptions` 가 곧 덱 목록이고,
"덱 필터"는 `item_occurrences(content_id)` 로 항목을 한정하는 것이다.

## Anki 와 같은 점 / 다른 점

| 구분 | 내용 |
|---|---|
| 같은 점 | 덱별 due·새 카드 카운트, 특정 덱만 골라 학습, 전체 학습(=모든 덱) |
| **다른 점** | 항목↔콘텐츠가 **다대다**(`item_occurrences`) — 같은 단어가 두 콘텐츠에 등장하면 그 카드의 due 는 **양쪽 덱에 모두 집계**된다 (Anki 는 카드가 정확히 한 덱에 소속) |
| 범위 밖 | 덱별 일일 목표/한도 — 오늘의 목표(daily_goal)는 전역 유지 |

## 덱 카운트 API (GET /api/study/decks)

구독한 콘텐츠만, 정렬 due DESC → title.

```json
{"items": [{"content_id": 1, "title": "...", "due": 3, "new_available": 5, "total_cards": 8}]}
```

| 필드 | 정의 |
|---|---|
| `due` | 지금 만기(`due_at <= now`)·미suspend 인 내 카드 수 — 해당 콘텐츠 등장 항목 한정 |
| `new_available` | 아직 내 카드가 없는 가시 항목 수 (큐가 새로 도입할 수 있는 양) |
| `total_cards` | 해당 콘텐츠 등장 항목에 대한 내 카드 수 (suspended 포함 — 학습 제외해도 카드는 내 것) |

세 카운트 모두 가시성 규칙(`visible_item_clause`)을 통과한 항목만 센다 —
구독 해제하면 덱이 목록에서 사라지고, 다시 담으면 카드 진행 상태 그대로 복귀.

## 덱 한정 학습 (GET /api/study/queue?content_id=N)

- `content_id` 지정 시 due 복습·신규 도입 모두 **해당 콘텐츠 등장 항목으로 한정**
  (`visible_item_clause` 는 그대로 AND — 가시성 규칙 우회 불가).
- 구독하지 않은/없는 `content_id` 는 404 (존재 여부 비노출 — my_contents 와 동일).
- 지정 시 응답에 `deck: {content_id, title}` 포함 (세션 헤더 표기용). 미지정 시 `null`.
- 일일 한도(daily_new_limit/daily_review_limit)·채점·등급 제출(`/answer`, `/rate`)은 불변 —
  덱 한정은 큐 구성 필터일 뿐이다.
- `introduced_today`(오늘 도입 수) 집계도 가시성 필터를 통과한 카드만 센다
  (9cccfee) — 담기 교체 직후 신규 예산이 비가시 카드에 잠겨 "복습할 카드가
  없어요"가 되는 버그 수정.

## 프론트

| 화면 | 동작 |
|---|---|
| 학습 허브 `/study` | "내 덱" 섹션 — 덱별 `due N · 새 카드 M` + [이 콘텐츠만 학습] → `/study/session?content=ID`. 기존 "오늘의 학습 시작"(전체=모든 덱)은 상단 유지 |
| 덱 0개 | "라이브러리에서 콘텐츠를 담아보세요" 빈 상태 + 라이브러리 링크 |
| 세션 `/study/session?content=ID` | 큐 API 에 `content_id` 전달, 헤더에 덱 이름 표기. 전체 학습이면 기존 그대로 |


덱 응답 `routine_done`(0~6, 2026-08-06): 갈아 넣기 루틴 진행 — 학습 탭이 진행 브릭과 라이브러리 상세 링크로 표시 (content-routine.md).
