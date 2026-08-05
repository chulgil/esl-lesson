# 스펙: 콘텐츠 루틴 여정 (이 영상 갈아 넣기)

> 작성: 2026-08-05 (구현 동시) · 기획: [ted-routine-2026-08.md](../proposal/ted-routine-2026-08.md)

카드 단위 학습(FSRS) 위에 **콘텐츠 단위 여정**을 얹는다 — TED 10단계 루틴의
듣기→분석→체화 3파트를 6단계 체크리스트로. 라이브러리 상세에서 진행한다.

## 6단계

| 단계 | 파트 | 내용 | CTA |
|---|---|---|---|
| 1 | 듣기 | 자막 없이 전체 듣기 (흐름만) | 수동 체크 |
| 2 | 듣기 | 중심 찾으며 다시 듣기 | 수동 체크 |
| 3 | 분석 | 문장 직해 — A-B 루프 구간 반복 | 수동 체크 (플레이어 병용) |
| 4 | 분석 | 추출 카드 학습 | `/study/session?content=ID` 링크 |
| 5 | 체화 | 섀도잉 (아래 3단 모드) | "시작" — 섀도잉 1단 켜고 플레이어로 |
| 6 | 체화 | 한 문장 요약 | 요약 제출 시 **자동 체크** (수동 체크 불가) |

## 섀도잉 3단 (플레이어 내장)

| 단 | 배속 | 자막 |
|---|---|---|
| 1 느리게 | 0.75x | 표시 |
| 2 원속도 | 1.0x | 표시 |
| 3 자막 없이 | 1.0x | **가림** (blur + "잠깐 보기" 버튼, 문장 바뀌면 다시 가림) |

"이해 후 섀도잉" 원리 — 가이드에서 5단계가 분석(3·4) 뒤에 놓인다.

## 한 문장 요약 (액티브 인출)

- 정오답이 아니라 **피드백형** — Claude(insight 모델)가 한국어 2문장: 잘한 점 1 +
  자연스러운 표현 제안 1 (점수·등급·훈계 금지). 프롬프트에 영상 도입부 스크립트
  12문장을 근거로 제공.
- **LLM 실패 시에도 저장은 진행** (feedback=null) — 인출 자체가 목적.
- 재제출 허용 — 이력 보존(`content_summaries`), 화면엔 최신 1건 표시.

## 데이터·XP

- `content_routine_progress(user_id, content_id, step)` — 행 존재=완료, 해제=삭제
  (uq user+content+step, 멱등)
- `content_summaries(user_id, content_id, text, feedback)` — 제출 이력
- XP (로그 실시간 파생 — `progress.routine_xp`): **완주(6단계) 콘텐츠 x 50 +
  요약 제출 x 20**

## API

| 메서드/경로 | 설명 |
|---|---|
| GET `/api/contents/{id}/routine` | `{steps:[{step,done}], completed, summary}` — 구독 콘텐츠만 (비구독 404) |
| POST `/api/contents/{id}/routine/{step}` | `{done}` 체크/해제 (step 1~6, 멱등) |
| POST `/api/contents/{id}/summary` | `{text}` → `{feedback}` — 저장 + 6단계 자동 체크 |

## 어원 (word-insight 확장, P1-4)

인사이트 페이로드에 `etymology_ko`(어근·접사 분해 한 줄) + `same_root`(같은 어근
단어 2~3) 추가 — 신규 생성분부터 (구 캐시는 필드 없음, UI 조건부 렌더).
