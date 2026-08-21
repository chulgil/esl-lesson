# 스펙: 사용 이벤트 로깅 (P1-D 관측 격차 해소)

> 작성: 2026-08-10 (구현 동시) · 기획: [proposal/effectiveness-audit-2026-08.md](../proposal/effectiveness-audit-2026-08.md) 4차 P1-D

서버 기록이 없어 사용률을 잴 수 없던 표면(말하기 녹음·방법 화면·주간 성적표·게임
오답 담기)의 **최소 파이어-앤-포겟 로깅**. 5차 검증의 측정 재료다.
분석은 SQL 로 한다 — 백오피스 UI 없음 (YAGNI).

## 이벤트 종류 (화이트리스트)

| kind | 시점 | meta |
|---|---|---|
| `record_compare` | 말하기 녹음 시작 (`RecordCompare`) | — |
| `method_view` | `/method` 열람 (로그인 사용자만 — 익명은 미기록) | — |
| `weekly_report_view` | 성적표 노출 1회 | `surface: home_banner \| study_tab` |
| `review_add` | 게임 오답 원탭 담기 (`ReviewPanel`) | `game: tetris \| quiz \| typing \| scramble \| dictation \| bingo` |
| `speech_check` | 발음 확인 시도 (`SpeechCheck` — 인식 결과 수신 시) | `grade: perfect \| good \| retry` |

`speech_check` 는 `speak_3` 미션의 집계 재료다 (retention `_quest_progress`) —
클라이언트 로그 파생이라 이론상 스푸핑 가능하지만 XP 20 저부담이라 허용
(pronunciation-scoring-2026-08 V1 결정).

새 표면 추가 시 `api/events.py` `KINDS` 에 등록 — 화이트리스트 밖은 422.

## 계약

- `POST /api/events` `{kind, meta?}` → 204. 로그인 필수(401), meta 는 최대 8키
  · 값 100자 (경계 검증 — zod 원칙).
- 클라이언트: `lib/usage.ts` `logUsage()` — 응답 대기 없음·실패 무시·`keepalive`.
  마운트 1회 기록은 `components/UsageBeacon.tsx`.
- 저장: `usage_events(user_id, kind, meta, created_at)` — 마이그레이션
  93ad7a71415a, 인덱스 `(kind, created_at)` + `user_id`.

## 조회 예 (5차 검증용)

```sql
SELECT kind, count(*), count(DISTINCT user_id)
FROM usage_events WHERE created_at > now() - interval '7 days'
GROUP BY kind;
```
