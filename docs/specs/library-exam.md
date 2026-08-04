# 스펙: 라이브러리 시험 (콘텐츠별 고정 시험지·랭킹)

> 최종 검증: 2026-07-31 (구현 기준 작성) · 설계 승인: 2026-07-31 (사용자, .harness spec locked)

라이브러리 콘텐츠마다 고정 시험지(최대 20문항 4지선다)를 제공해 **응시 -> 서버 채점 -> 콘텐츠별 최고점 랭킹 -> 시험 업적·테마 보상**으로 이어지는 경쟁 루프를 만든다. 문항은 생성 시점 스냅샷으로 고정되어 모든 응시자가 같은 문제로 경쟁한다.

## 아키텍처 결정

| 결정 | 근거 | 기각한 대안 |
|---|---|---|
| 문항 JSONB 스냅샷 (`exam_questions.payload`) | 원본 항목 수정/거절과 무관하게 채점 자립 — 회차 내 공정성 보장 | 응시마다 랜덤 출제 — 경쟁 공정성 훼손 (인터뷰 확정) |
| attempt 시작-제출 2단계, duration 서버 계산 | 클라 시간 조작 차단 — 랭킹 공정성 | 클라 duration 신뢰 — 조작 가능 |
| 랭킹 실시간 집계 (window function) | 업적·XP 와 동일 원칙 — 적립 테이블 없음, 소급 정합 | 랭킹 캐시 테이블 — 규모상 불필요, 정합 리스크만 추가 |
| pattern 문항 4지선다 변환 (해석->문장 고르기) | 시험은 마킹형 통일 (OMR 컨셉) — 칩 조립은 학습 모드 전용 | 시험에 칩 조립 혼재 — 채점·UI 복잡도 상승 |
| 진행 중 attempt 는 archived 후에도 제출 허용 | 시작한 시험지를 마칠 권리 — 그 회차 랭킹에 반영 | 제출도 차단 — 회차 전환 경합 시 응시분 증발 |

## 데이터 모델 (e6f7a8b9c0d1, 2026-07-31)

```
exams                       -- 시험지 회차. 콘텐츠당 active 1개
  id BigInt PK
  content_id FK             -- contents.id, ondelete CASCADE
  round Int                 -- 1부터 증가. unique(content_id, round)
  status Text               -- "active" | "archived"
  question_count Int        -- 스냅샷 문항 수 (기본 20, 항목 부족 시 실제 수)
  created_by FK nullable    -- users.id, SET NULL
  created_at

exam_questions              -- 문항 스냅샷 (원본 변경과 무관하게 고정)
  id BigInt PK
  exam_id FK                -- exams.id, CASCADE. unique(exam_id, seq)
  seq Int                   -- 1..N 출제 순서
  item_id FK nullable       -- learning_items.id, SET NULL (참조용 — 채점은 payload)
  payload JSONB             -- {quiz_mode, prompt, prompt_ko?, choices[4], answer_index, en_text, ko_text}

exam_attempts               -- 응시 1회. 인덱스 (exam_id, user_id)
  id BigInt PK
  exam_id FK / user_id FK   -- 둘 다 CASCADE
  started_at                -- 응시 시작 = attempt 생성 (서버 시각)
  submitted_at nullable     -- NULL = 진행 중/이탈 (만료 없음, 랭킹 무영향)
  score / correct_count / duration_ms / answers  -- 제출 시 채워짐
```

- 출제(`services/exams.py create_exam`): 해당 콘텐츠 ItemOccurrence 의 **승인 항목(word/idiom/pattern)** 에서 셔플 후 최대 20개. 문항 생성은 `services/quiz.py build_question` 재사용, pattern 은 4지선다로 변환(정답 = 대표 출처 문장, 오답 = 다른 항목 문장). 항목 5개 미만이면 생성 거부(422).
- 재생성 = 기존 active -> archived + round+1. 이전 회차의 랭킹·응시 이력은 읽기 전용 보존.
- 랭킹 = 유저별 best 1행(`score DESC, duration_ms ASC, submitted_at ASC` row_number) 실시간 집계 — 콘텐츠당 수천 건 규모까지 단일 쿼리.

## API

| 메서드/경로 | 역할 |
|---|---|
| GET /api/exams/open | 열린 시험 목록 (active 만, 최신순) — content_title/응시자 수/my_best/top_name. 학습 허브 도전 카드·라이브러리 시험 칩용 (2026-07-31) |
| GET /api/contents/{id}/exam | 활성 시험 요약 — exam_id/round/question_count/응시자 수/my_best/TOP3. 없으면 `{exam_id: null}` |
| POST /api/exams/{id}/attempts | 응시 시작 — attempt 생성 + 정답 없는 문항 + started_at. archived 409 `exam_archived`. **본인 기존 미제출 attempt 는 선삭제** (방치 시 제출 후에도 "이어서 응시" 영구 재등장 — 2026-07-31 재검토) |
| GET /api/exams/{id}/attempts/{aid} | **진행 중 응시 재개** (2026-07-31) — 서버 저장 started_at·문항 복원. 본인·미제출만, 그 외 404 |
| DELETE /api/exams/{id}/attempts/{aid} | **응시 포기(초기화)** — 미제출 attempt 삭제(랭킹 무영향), 경과 리셋. 제출분 409. 미제출 조건을 DELETE WHERE 에 포함한 **원자 실행** — read-then-delete 는 동시 submit 과 경합해 랭킹 반영분을 지운다 (2026-07-31 재검토) |
| POST /api/exams/{id}/attempts/{aid}/submit | 서버 채점 — score=정답수x5, duration 서버 시각차. 결과+순위+복기+**xp_gained**. 1위가 바뀌면 이전 1위에게 `exam_dethroned` 알림 (자기 갱신·최초 등극 제외) |
| GET /api/exams/{id}/rankings | TOP 50 + 내 순위(me) — nickname 없으면 name 폴백, is_me 플래그 |
| POST /api/admin/contents/{id}/exam | 생성/재생성 (require_admin). 부족 422 `not_enough_items` |
| GET /api/admin/contents/{id}/exams | 회차 목록 + 문항 미리보기 (정답 포함 — 검수용) |

오류 계약: answers 경계 검증(길이=문항 수, 각 값 0..3) 422 `invalid_answers` · 중복 제출 409 `already_submitted` · 타인/미존재 attempt 404 (존재 비노출) · archived 새 응시 409 (**진행 중 attempt 제출은 허용** — 해당 회차 랭킹 반영).

## XP 보상 (2026-07-31 — "시험 보고 싶게" 기획)

- **제출당 20 XP** (게임 참여와 동급) + **점수 10점당 1 XP** (만점 +10) — 재응시도 매번 지급 (반복 학습 유도).
- 산식 정본: `api/exams.py exam_xp()` = stats 의 시험 XP 합산과 동일. **건별 floor(score/10) 합** — 합계에 //10 하면 어긋난다.
- 결과 화면에 "+N XP 획득!" 즉시 표시 (`ExamResult`).

## 경쟁 루프 (2026-07-31)

- **1위 탈환 알림**: submit 에서 이전 1위(이 attempt 제외 best)와 새 1위를 비교 — 새 1위 = 나 && 이전 1위 != 나 일 때만 이전 1위에게 `exam_dethroned` `{content_id, content_title, by_name}` 적재. 벨 문구 "{by} 님이 '{제목}' 시험 1위를 가져갔어요 — 되찾으러 가볼까요?", 탭 -> /exam/{content_id}.
- **발견성**: 학습 허브 "시험 도전" 섹션(응시자 수·1위 이름·내 최고점/미응시·[도전하기]) + 라이브러리 카드 시험 칩("시험 도전 · 1위 {name}" / "내 최고 N점" / "첫 도전자가 돼보세요").

## 업적 (family "exam") · 테마 보상

| key | title | target/tier | metric |
|---|---|---|---|
| first_exam | 첫 시험 | 1 (단발) | 제출 수 |
| exam_perfect | 만점 | 1 (단발) | score 100 응시 존재 |
| exam_champion | 1위 등극 | 1 (단발) | 현재 1위인 시험 존재 — **공동 1위 = best score 동률 (duration 무관)** |
| exams_10/30/100 | 응시 입문/중수/고수 | 10/30/100 (초/중/고급) | 제출 수 |

- 집계는 제출 완료 attempt 만 (`achievements.compute` — 진행 중/이탈 무영향). 순위를 뺏기면 champion 스티커는 꺼질 수 있으나 테마 grant 는 영구 (theme-mall.md 기존 원칙).
- 테마 보상: `theme_reward_rules` 에 exam 업적 키를 매핑하면 기존 `sync_theme_rewards` 가 그대로 지급 — **엔진 무수정** (예: exam_perfect -> excel).

## 경과 시계·재개 (2026-07-31)

- 응시 화면 헤더에 경과 mm:ss — **기준은 서버 started_at** (화면 이탈·새로고침에도 이어짐). 표시는 안내용, 판정은 서버 duration.
- 시계 컨셉은 테마별 (`theme-surfaces CLOCK_OF`): 노트·학교=벽시계 / 캔디=막대사탕 / 레고=디지털 브릭 / 헤냥이=고양이 / 오피스=상태바 셀. 분침·초침 실회전.
- 요약에 `my_open_attempt` — intro 에서 [이어서 응시 (경과 계속)] + [새로 시작], 응시 중 [포기하기 (경과 초기화)]. 마킹은 localStorage(attempt 단위) 임시 저장 — 제출·포기 시 제거.
- 시험지 표면은 테마별 스킨 (`theme-surfaces SURFACE_SKINS`): 노트=종이 시험지 / 캔디=파스텔 사탕판 / 레고=블록판 / 헤냥이=크림 고양이 카드(발도장·살구 젤리) / 오피스=평가서 시트 / 학교수업=갱지 시험지. **컨셉은 테마마다 배타적** — 칠판은 학교수업만 쓴다 (2026-08-04: 헤냥이가 칠판을 쓰고 있어 학습·시험 화면에서만 고양이 세계관이 끊겼다).

## 프론트

| 경로 | 내용 |
|---|---|
| 라이브러리 상세 | `ExamEntryCard` — [시험 보기] + 요약(응시자·내 최고점·TOP3). 시험 없으면 "시험 준비 중" |
| /exam/[contentId] | OMR 시험지 — 문항 카드 + 답안 마킹 그리드(모바일 하단 고정, `OmrGrid`), 진행/남은 문항 표시. 제출 -> 결과(`ExamResult` 점수 도장·복기·순위·[다시 도전]·[랭킹 보기]) |
| 랭킹 (`ExamRankings`) | TOP 50 + 내 순위 고정행, 1위 왕관 |
| 백오피스 콘텐츠 상세 [시험] 탭 | `ExamPanel` — 생성/재생성(422 안내), 회차 목록·문항 미리보기(정답 하이라이트) |
| 스티커 벽 | `AchievementBadges` FAMILY_ORDER 에 "exam"("시험") — 시험지/메달/왕관 아이콘 |

API 클라: `frontend/src/lib/exam-api.ts` (summary/start/submit/rankings) + `admin-api.ts` (createExam/listExams).

## 범위 외 (후속)

시험 제한시간(타이머 강제 종료 — 소요시간은 기록만) · 문항 수동 편집(재생성으로 갈음) · 주간/시즌 랭킹 리셋(회차 갱신이 대체).

## 테스트

`backend/tests/test_exams.py` (모델·생성 스냅샷/422/재생성·응시 시작/제출 채점/경계 422·409·404/archived 경합·랭킹 동점/폴백) + `test_achievements.py` exam 3케이스 + `test_themes.py::test_exam_achievement_grants_theme`. 회귀 eval: `.harness/evals/library-exam.toml` 4케이스.
