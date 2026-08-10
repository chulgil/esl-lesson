# 주간 성적표 (P1 리텐션 — 증거 기둥 집계)

> 작성: 2026-08-07 (effectiveness-audit-2026-08.md 구멍 5 격상분)

> 일 단위 증거(세션 완료 화면·장기 기억 배지)는 있는데 **주 단위 서사가 없어**
> 7일차 이탈 시나리오("이게 느는 건가")의 대응이 비어 있었다. 매주 월요일(KST),
> "지난주의 나 vs 그 전주의 나"를 델타 중심으로 돌려준다.

## 원칙

- **스냅샷 테이블 없음** — 전 지표를 기존 로그(`review_logs`,
  `content_routine_progress`, `listen_checks`)에서 매 호출 실시간 파생.
  산식이 바뀌어도 과거가 소급 반영된다 (장기 기억 지표와 동일 원칙).
- **델타 중심 카피** — 절대치보다 변화("지난주보다 +12"). 비교 대상이 없으면
  (전주 복습 0) 델타를 말하지 않는다 — 0% 에서 올랐다고 말하지 않는다.
- **빈 성적표는 보내지 않는다** — 지난주 복습 0건이면 푸시·배너·카드 전부 숨김
  (`has_data` 게이트). 할 일 없는 알림은 이탈 유발 (push-reminder.md 와 동일).

## 산출 (GET /api/study/weekly-report)

대상 주 = 지난주 월~일 (KST). 경계는 KST 자정을 UTC 로 환산해 로그 저장
규칙(UTC)과 맞춘다.

| 필드 | 값 | 델타 |
|---|---|---|
| `reviews` | 지난주 복습 수 | `reviews_delta` (vs 그 전주) |
| `accuracy` | 정답률 % (복습 0 이면 null) | `accuracy_delta` (양쪽 다 있을 때만, 아니면 null) |
| `long_term_new` | 간격 7일+ 첫 도달 카드 수 | `long_term_new_delta` |
| `routine_steps` | 루틴 단계 완료 수 | `routine_steps_delta` |
| `listen` | 재청취 이해도 `{delta, contents}` — stage 2 를 지난주에 찍은 콘텐츠의 전후 평균 차. 비교쌍 없으면 null | (자체가 델타) |
| `streak_days` | 현재 스트릭 (stats 와 동일 파생 — 책갈피 포함) | — |
| `has_data` | 지난주 복습 1개 이상 | 노출 게이트 |

## 노출 3곳

| 표면 | 시점 | 규칙 |
|---|---|---|
| **월요일 푸시** | 월요일(KST) `reminder_hour` 이후, 10분 주기 평가 | 사용자 단위 주 1회 — `user_settings.weekly_report_week` 에 대상 주 ISO 기록 (책갈피 주간 지급 가드와 같은 패턴). 리마인더의 기기별 dedup 과 달리 성적표는 **사람에게 한 번인 사건**. 복습 0건이면 발송·마킹 모두 안 함 — 로그가 소급되면 같은 월요일 안에 재평가 |
| **홈 배너 1회** | 새 성적표가 나온 주의 첫 방문 | 복귀 감사 배너와 동일 패턴 — localStorage `esl:weekly-report:seen` 에 `week_start` 기록, 표시 즉시 기록(두 번 조르지 않기). 모달 금지, 조용한 한 줄 + `/study` 링크. 이미 본 주면 API 호출 자체를 생략 |
| **학습 탭 카드** | 상시 (그 주 내내) | `has_data` 일 때만. 델타 중심 수치 + 다음 주 제안 1줄 |

## 카피 규칙

- 델타 중심: "복습 121개 — 지난주보다 +12" (델타 0 이면 수치만).
- 재청취 델타가 있으면 강조 — 앱 밖 감각의 증거가 최상위 서사.
- **다음 주 한 줄 제안 1개** (규칙 파생, 프론트 계산 — LLM 아님):
  복습 감소 → 최소 행동 바닥 / 루틴 0 → 정복 시작 / 재청취 없음 → 체크
  권유 / 그 외 → 리듬 유지.
- **최소 행동 바닥 고지 필수**: "1개만 해도 스트릭은 이어져요" — 스트릭이
  복습 1개로 유지된다는 사실을 사용자에게 말하는 유일한 곳 (3차 감사).

## 구성 요소

- **서비스**: `app/services/weekly_report.py` — `build()` (전체 성적표),
  `review_counts()` (푸시 게이트용 경량 조회), `last_week_start()` (KST 월요일)
- **API**: `GET /api/study/weekly-report` (`app/api/study.py`)
- **푸시**: `app/services/push.py` — `send_weekly_reports()` + `weekly_report_payload()`
  (`{title, body, url:"/study", tag:"weekly-report"}` — 서비스 워커 계약 동일)
- **워커**: `app/workers/reminders.py` — 리마인더와 같은 10분 루프에 얹음
  (월요일·주 1회 게이트는 서비스가 판단)
- **모델**: `user_settings.weekly_report_week` (Text, ISO 주) — 마이그레이션 `9a3c7d21e4b8`
- **프론트**: `components/study/WeeklyReportCard.tsx` (학습 탭) +
  `components/study/WeeklyReportBanner.tsx` (홈 1회) + `studyApi.weeklyReport()`
