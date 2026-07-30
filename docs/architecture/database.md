# 데이터베이스 설계

> 최종 검증: 2026-07-30 (코드 대조 완료)

서버 기존 PostgreSQL 17 컨테이너(`postgres`, pgvector/pg17)에 **데이터베이스 `englesson` + 전용 롤 `englesson`** 을 추가한다. 기존 서비스와 컨테이너는 공유하되 DB/권한은 격리한다.

## 공통 규칙

- PK: `BIGINT GENERATED ALWAYS AS IDENTITY`
- 시각: `timestamptz`, **UTC 저장** (표시 시 KST 변환 — 프로젝트 공통 규칙)
- enum: PG 네이티브 enum 대신 `text + CHECK` (Alembic 마이그레이션 단순화)
- 마이그레이션: Alembic 단일 head 유지, 배포 시 `alembic upgrade head` 자동 실행

## ERD

```
users 1--N review_cards N--1 learning_items
users 1--N contents (created_by)
users 1--N review_logs
users 1--1 user_settings

contents 1--N transcript_segments
contents 1--N extraction_jobs
contents 1--N item_occurrences N--1 learning_items

review_cards 1--N review_logs

users 1--N game_matches (player1/player2)
```

(ERD 는 핵심 학습 도메인만. 이후 추가된 확장 테이블은 아래 "확장 테이블" 참조.)

핵심 설계 결정 — **학습 항목은 전역(global)으로 중복 제거**한다. 같은 단어 "resilient"가 영상 3개에 나와도 `learning_items` 행은 1개, 출처는 `item_occurrences`로 연결. 사용자는 항목당 카드 1장만 가진다(중복 학습 방지).

## 테이블 정의

### users — 사용자

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| id | bigint | PK | |
| google_sub | text | UNIQUE NOT NULL | Google OAuth `sub` 클레임 |
| email | text | UNIQUE NOT NULL | |
| name | text | NOT NULL | |
| nickname | text | DEFAULT '' | 게임/친구 표시명 (실명 비노출 — a3b4c5d6e7f8) |
| avatar_url | text | | |
| role | text | CHECK IN ('admin','learner'), DEFAULT 'learner' | 백오피스 접근 = admin |
| created_at / last_login_at | timestamptz | | |

최초 관리자: 환경변수 `ADMIN_EMAILS`(콤마 구분)에 등록된 이메일은 첫 로그인 시 role=admin 부여.

### user_settings — 학습 설정

| 컬럼 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| user_id | bigint | PK, FK users | |
| daily_new_limit | int | 20 | 하루 신규 카드 도입 한도 |
| daily_review_limit | int | 200 | 하루 복습 한도 |
| daily_goal | int | 20 | 일일 목표 (c5d6e7f8a9b0) |
| desired_retention | real | 0.90 | FSRS 목표 기억률 |
| hint_delay_seconds | int | 10 | 힌트 노출 지연 (d4e5f6a7b8c9) |
| study_level | int | 2 | 학습 레벨 프리셋 (e5f6a7b8c9d0) |
| levels_enabled | int[] | {1,2} | 학습할 항목 타입 선택 |
| streak_savers / saver_award_week | int / text | 0 / NULL | 스트릭 세이버 (a9b0c1d2e3f4) |

### contents — 콘텐츠 (유튜브/수기)

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| id | bigint | PK | |
| source | text | CHECK IN ('youtube','manual') | |
| visibility | text | CHECK IN ('public','private'), DEFAULT 'public' | 공용/개인 (b2c3d4e5f6a7 — content-governance.md) |
| youtube_video_id | text | UNIQUE (NULL 허용) | 11자 비디오 ID, 중복 등록 방지 |
| youtube_license | text | NULL 허용 | 'creativeCommon'/'youtube' — Data API 조회 (c9d0e1f2a3b4) |
| url | text | | 원본 URL |
| title | text | NOT NULL | 유튜브면 자동 기입 |
| title_ko | text | | AI 번역 제목 (선택) |
| status | text | CHECK IN ('pending','extracting','ready','failed') | 파이프라인 상태 |
| error_message | text | | status=failed 시 |
| created_by | bigint | FK users | 등록 관리자 |
| created_at / updated_at | timestamptz | | |

### transcript_segments — 스크립트 (영/한 병렬)

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| id | bigint | PK | |
| content_id | bigint | FK contents ON DELETE CASCADE | |
| seq | int | UNIQUE(content_id, seq) | 문장 순서 |
| start_ms / end_ms | int | NULL 허용 | 유튜브 타임스탬프 (수기는 NULL) |
| en_text | text | NOT NULL | |
| ko_text | text | | 없으면 AI 번역으로 채움 |
| words | jsonb | NULL 허용 | 단어 단위 타임스탬프 정렬 (b1c2d3e4a5f6 — word-alignment.md) |

### learning_items — 학습 항목 (전역 중복 제거)

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| id | bigint | PK | |
| item_type | text | CHECK IN ('word','idiom','pattern','sentence') | 레벨 1/2/3/4 대응 |
| en_text | text | NOT NULL | 단어/숙어/패턴/문장 원문 |
| ko_text | text | NOT NULL | 뜻/번역 |
| normalized_key | text | UNIQUE(item_type, normalized_key) | 소문자/공백정규화 — 전역 dedup 키 |
| hint_thinking | text | | "영어식 사고" 힌트 (문장 타입 필수, 예: "그 나무가 있다, 저기에") |
| pattern_template | text | | 패턴 타입 전용 (예: `It takes ___ to ...`) |
| difficulty_hint | text | CHECK IN ('basic','intermediate','advanced') | AI 추정 난이도. basic은 추출 시 제외 원칙 |
| review_status | text | CHECK IN ('pending','approved','rejected'), DEFAULT 'pending' | 관리자 검수 상태. approved만 학습 풀 편입 |
| extra | jsonb | DEFAULT '{}' | 품사, 발음기호, 예비 필드 |
| created_at / updated_at | timestamptz | | |

### item_occurrences — 항목 출처 (항목 ↔ 콘텐츠)

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| id | bigint | PK | |
| item_id | bigint | FK learning_items ON DELETE CASCADE | |
| content_id | bigint | FK contents ON DELETE CASCADE | |
| segment_id | bigint | FK transcript_segments | 출처 문장 (문맥 제시용) |
| context_en / context_ko | text | | 출처 문장 스냅샷 |

UNIQUE(item_id, content_id, segment_id)

### review_cards — 사용자별 FSRS 카드

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| id | bigint | PK | |
| user_id | bigint | FK users, UNIQUE(user_id, item_id) | |
| item_id | bigint | FK learning_items | |
| state | text | CHECK IN ('new','learning','review','relearning') | FSRS 상태 |
| due_at | timestamptz | NOT NULL | 다음 복습 시각 |
| stability | real | | FSRS S |
| difficulty | real | | FSRS D |
| reps / lapses | int | DEFAULT 0 | 총 복습 / 망각 횟수 |
| suspended | boolean | DEFAULT false | 학습 제외 토글 |
| fsrs_json | jsonb | NULL 허용 | py-fsrs Card 직렬화 원본 (a1b2c3d4e5f6). state/stability 등은 프로젝션 |
| last_review_at / created_at | timestamptz | | |

### review_logs — 복습 이력 (FSRS 재최적화 원천 데이터)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | bigint | PK |
| card_id / user_id | bigint | FK |
| rating | smallint | 1=Again, 2=Hard, 3=Good, 4=Easy |
| correct | boolean | 퀴즈 정답 여부 |
| answer_text | text | 사용자 입력 (레벨 4 서술형) |
| quiz_mode | text | 'choice_ko2en', 'choice_en2ko', 'cloze', 'pattern', 'compose' 등 |
| duration_ms | int | 응답 소요 시간 |
| state_before | text | 복습 전 카드 상태 |
| scheduled_days / elapsed_days | real | FSRS 로그 표준 필드 |
| reviewed_at | timestamptz | |

### extraction_jobs — 파이프라인 단계 추적

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | bigint | PK |
| content_id | bigint | FK contents |
| step | text | 'metadata' / 'transcript' / 'translate' / 'extract' / 'embed' / 'align' |
| status | text | 'pending' / 'running' / 'done' / 'failed' |
| attempt | int | 재시도 횟수 (최대 3) |
| error | text | 실패 사유 |
| payload | jsonb | 단계별 산출물 요약/로그 |
| started_at / finished_at | timestamptz | |

### game_matches — 대전 기록 (워드 테트리스)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | bigint | PK |
| mode | text | 'pvp' / 'pve' |
| status | text | 'waiting' / 'playing' / 'finished' / 'aborted' |
| room_code | text | PvP 초대 코드 (6자) |
| player1_id / player2_id | bigint | FK users (PvE는 player2 NULL) |
| bot_level | smallint | PvE 봇 난이도 1-5 |
| winner_id | bigint | NULL=무승부/중단 |
| p1_score / p2_score | int | |
| stats | jsonb | WPM, 콤보, 정확도, 처리 단어 수 |
| started_at / ended_at | timestamptz | |

## 확장 테이블 (2026-07 추가 — 상세 컬럼은 모델 파일 참조)

| 테이블 | 용도 | 모델 파일 / 스펙 |
|--------|------|------------------|
| content_permissions | 저작권 이용허락 기록 (범위 4종 + 증빙) | `models/content.py` / content-governance.md |
| content_subscriptions | 라이브러리 담기(구독) — UNIQUE(content_id, user_id) | `models/content.py` / study-decks.md |
| word_insights | 단어 인사이트 카드 (AI 생성, 항목당 1회) | `models/item.py` / word-insight.md |
| item_embeddings | pgvector halfvec(1024) + HNSW (유사단어/오답 선지) | 마이그레이션 a7b8c9d0e1f2 / word-insight.md |
| friendships | 친구 관계 (요청/수락) | `models/friend.py` / chat.md |
| conversations / chat_messages / chat_reads | 1:1 채팅 (메시지·읽음) | `models/chat.py` / chat.md |
| push_subscriptions | 웹 푸시 구독 (VAPID) | `models/push.py` / push-reminder.md |
| notifications | 알림 센터 적재 (type + payload JSONB + read_at) | `models/notification.py` / notifications.md |
| theme_grants | 제한 테마 지급 — UNIQUE(user_id, theme_key) | `models/theme.py` / theme-mall.md |
| streak_saver_uses / quest_completions | 리텐션 팩 (스트릭 세이버·퀘스트) | `models/retention.py` / learning.md |
| typing_races | 타자 레이스 기록 | `models/game.py` / typing-race.md |
| scramble_races | 스크램블 레이스 기록 | `models/game.py` / scramble-race.md |
| dictation_races | 딕테이션 배틀 기록 | `models/game.py` / dictation-battle.md |
| daily_puzzle_plays | 데일리 퍼즐 플레이 기록 | `models/game.py` / daily-puzzle.md |
| quiz_royale_matches / quiz_royale_players | 퀴즈 로얄 매치·정규화된 플레이어 집계 | `models/game.py` / quiz-royale.md |

## 인덱스

```sql
-- 학습 큐 조회 (가장 빈번한 쿼리)
CREATE INDEX idx_cards_due ON review_cards (user_id, due_at)
  WHERE NOT suspended;

-- 검수 대기 목록
CREATE INDEX idx_items_review ON learning_items (review_status, item_type);

-- 파이프라인 모니터링
CREATE INDEX idx_contents_status ON contents (status);
CREATE INDEX idx_jobs_content ON extraction_jobs (content_id, step);

-- 통계 (일별 복습 수)
CREATE INDEX idx_logs_user_time ON review_logs (user_id, reviewed_at);
```

## DB/롤 초기화 (1회, 서버에서 수동 실행)

```sql
CREATE ROLE englesson LOGIN PASSWORD '<시크릿에서 주입>';
CREATE DATABASE englesson OWNER englesson ENCODING 'UTF8';
```

애플리케이션 접속 문자열: `postgresql+asyncpg://englesson:***@postgres:5432/englesson`
(backend 컨테이너를 기존 도커 네트워크에 연결해 컨테이너명 `postgres`로 접속. 상세: [deployment.md](deployment.md))

## 마이그레이션 정책

- 모든 스키마 변경은 Alembic 리비전으로만 (수동 DDL 금지, 위 초기화 1회 제외)
- 배포 파이프라인에서 컨테이너 기동 전 `alembic upgrade head` 실행
- 파괴적 변경(컬럼 삭제 등)은 2단계 배포 (구버전 호환 유지 → 다음 릴리스에서 제거)

## DB 설계 감사 (2026-07-15)

### 패러다임 매핑 — 현행 유지 판정

| 요구 | 채택 | 근거 |
|---|---|---|
| 핵심 도메인 (사용자·카드·로그·콘텐츠) | RDB (정규화 + FK + CHECK) | 정합성·조인이 본질인 데이터 |
| 결과 스냅샷 (게임 stats, FSRS 상태, 인사이트) | JSONB 컬럼 | 스키마 유동적·행 단위 조회 전용. 단, **집계는 JSONB 금지** (아래) |
| 단어 임베딩 유사도 | pgvector halfvec(1024) + HNSW | 전용 VectorDB 불필요 — 데이터 수만 건 규모, 코사인 top-k 는 HNSW 로 충분 |
| 어휘망 그래프 | SQL(LATERAL top-k) + 앱 조립 | 노드 300 캡·1-hop 조회뿐 — GraphDB 는 운영 비용만 추가 |

별도 NoSQL/GraphDB/VectorDB 인스턴스를 두지 않는 것이 **의도된 결정** —
2GB 단일 서버에서 PostgreSQL 확장(JSONB/pgvector)으로 전 요구를 충족한다.

### 감사에서 고친 것 (리비전 b4c5d6e7f8a9)

- **인덱스 보강 11개**: PG 는 FK 자동 인덱스가 없다 — 쿼리 근거 있는 컬럼만 선별
  (occurrences.content_id 는 모든 학습 쿼리의 가시성 서브쿼리에 포함되어 최우선).
- **quiz_royale_players 정규화**: XP·최고기록·업적·리더보드가 players JSONB 를
  파이썬에서 풀스캔(매 페이지뷰 O(전체 매치)) → 인덱스 집계로 전환. JSONB 는
  결과 화면 스냅샷으로만 유지. 기존 데이터 백필 포함.
- **경합 방어**: SELECT-후-INSERT 경로(큐 신규 카드 도입·유사단어 추가·푸시 구독)에
  IntegrityError → rollback → 승자 채택 폴백. UNIQUE 제약이 최종 심판.

### 스케일 노트 (재검토 트리거)

- 커넥션: 단일 api 프로세스, SQLAlchemy 기본 풀(5+10) + pre_ping — PG max_connections 여유.
- review_logs 는 append-only 로 최대 성장 — (user_id, reviewed_at) 인덱스로 통계는
  유저 범위 스캔. **월 100만 행 초과 시** 일별 집계 테이블(materialized) 검토.
- 주간 리더보드는 요청마다 7일 창 집계 — **DAU 수백 초과 시** 캐시(60s) 또는
  집계 테이블 검토. 현재 규모(수십 명)에서는 과설계.
