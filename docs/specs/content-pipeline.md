# 스펙: 콘텐츠 파이프라인 (유튜브 추출 + AI 학습 항목 추출)

> 최종 수정: 2026-07-11

유튜브 URL 또는 수기 입력으로 등록된 콘텐츠에서 영어/한글 스크립트를 확보하고, Claude API로 학습 항목 4종(단어/숙어/패턴/문장)을 추출해 DB에 저장한다.

## 콘텐츠 가시성 (2026-07-11 요구사항 추가)

| 구분 | 등록 위치 | visibility | 추출 항목 편입 | 노출 범위 |
|------|-----------|------------|----------------|-----------|
| 공용 | 백오피스 (admin) | `public` | 관리자 검수(승인) 후 | 전체 사용자 |
| 개인 | 서비스 (`/my`) | `private` | **자동 편입** (검수 없음) | 등록자 본인만 |

- 개인 등록 일일 한도: **10건/일** (KST 기준, 관리자 무제한) — AI 비용 보호. 초과 시 429.
- 항목(learning_items)은 전역 dedup 유지. 노출 규칙: "공용 콘텐츠에 출처가 있는 승인 항목" ∪ "내 개인 콘텐츠에 출처가 있는 항목(rejected 제외)".
- 개인 항목 제외는 검수 상태가 아니라 **본인 카드 suspend** 로 처리 (항목이 공용과 공유될 수 있으므로 전역 상태를 개인이 바꾸지 않는다).
- 공개 전환(개인→공용)은 이번 범위 제외 (2026-07-11 사용자 결정). 단, 관리자가 이미 개인 등록된 영상을 백오피스에서 등록하면 **공용 승격** (재추출 없음).

### 공용 승격 CC 라이선스 게이트 (2026-07-14 저작권 검토)

공용 = 전 회원 전송이므로 **크리에이티브 커먼즈(CC BY) 영상만 기본 허용**한다.

- `contents.youtube_license` (Data API `status.license`: `creativeCommons` | `youtube` |
  NULL 미확인). 파이프라인 metadata 단계에서 자동 조회 (`YOUTUBE_API_KEY` 필요,
  미설정 시 NULL 유지 — 공식 Data API 라 약관 안전)
- 백오피스 공용 등록/승격 시 CC 가 아니면(미확인 포함) **409 `cc_required`** —
  UI 에서 "권리자 허락을 확인했어요" 오버라이드(`allow_non_cc`)로만 진행 가능
- 개인(private) 등록은 게이트 미적용 (본인 학습용 — 사적 이용 범주)
- 기존 콘텐츠 백필: `scripts/backfill_licenses.py`

### 구독 구조 (2026-07-11 추가)

같은 유튜브 영상은 콘텐츠 1행을 공유하고 `content_subscriptions(content_id, user_id)` 로 사용자와 연결한다.

- 이미 등록된 영상을 다른 사용자가 등록 → 구독만 추가, **재추출 없이 즉시 사용** (AI 비용 0, 일일 한도 미차감)
- 일일 한도(10건)는 **신규 생성(추출 비용 발생)만** 카운트
- "내 콘텐츠" 목록/상세/게임 소재/항목 노출 전부 구독 기준
- 구독 해지: 마지막 구독자가 떠난 개인 콘텐츠는 본체 삭제, 공용은 유지
- 삭제 기획 (2026-07-16): 삭제한 콘텐츠의 항목은 **향후 학습 목록에서만 빠지고**
  (가시성 규칙 — 출처 없음), 연습 기록(review_cards·review_logs)은 보존.
  같은 항목을 재등록하면 FSRS 진행 상태가 그대로 이어진다.
  목표 — 학생이 관심 있는 콘텐츠로 학습하되, 콘텐츠를 정리해도 실력 기록은 유지

## 입력 경로 2가지

| 경로 | 입력 | 자동 처리 |
|------|------|-----------|
| 유튜브 URL | URL 1개 | 제목 자동 기입 + 영/한 자막 추출 + (한글 없으면) AI 번역 + 4종 추출 |
| 수기 입력 | 제목 + 영어 스크립트 + 한글 스크립트(선택) | (한글 없으면) AI 번역 + 4종 추출 |

## 상태 머신 (contents.status)

```
pending ──> extracting ──> ready
                │
                └────────> failed ──(관리자 재시도)──> extracting
```

- 등록 API는 행 생성 후 **즉시 202 반환** — 추출은 백그라운드 워커가 수행.
- 단계별 진행/실패는 `extraction_jobs`에 기록 → 백오피스에서 단계 단위로 확인/재시도.
- 재시도: 단계당 자동 3회 (지수 백오프 5s/25s/125s), 이후 failed 확정.

## 단계 1: 메타데이터 (유튜브만)

- 비디오 ID 파싱: `watch?v=`, `youtu.be/`, `shorts/`, `embed/` 형식 지원. 파싱 실패 시 등록 자체를 400으로 거부.
- 제목 조회: YouTube oEmbed(`https://www.youtube.com/oembed?url=...`) — API 키 불필요. 실패 시 yt-dlp 메타데이터로 폴백.
- 중복 방지: `youtube_video_id` UNIQUE — 이미 등록된 영상이면 409 + 기존 콘텐츠 링크 반환.

## 단계 2: 자막 추출 (유튜브만)

```
youtube-transcript-api 로 자막 목록 조회
  ├─ en 수동 자막 있음        → 채택 (최우선)
  ├─ en 자동 생성 자막만 있음  → 채택 (품질 경고 플래그)
  └─ en 계열 전무             → 실패 처리 + "수기 입력으로 전환" 안내
ko 자막 있으면 함께 추출 (수동 > 자동 우선)
차단/오류 시 yt-dlp 자막 다운로드로 1회 폴백
```

문장 재구성: 자막 조각(캡션 단위)은 문장 중간에서 끊기므로, 타임스탬프를 보존한 채 문장부호 기준으로 병합해 `transcript_segments`(seq, start_ms, en_text)로 저장한다. 자동 자막(문장부호 없음)은 단계 3 번역 호출에 문장 분리를 함께 요청한다.

## 단계 3: 한글 번역 (ko 스크립트 부재 시)

- Claude API로 세그먼트 배치 번역(한 번에 ~50 세그먼트, JSON in/out).
- 유튜브 ko 자막이 있으면 이 단계는 건너뛰고 타임스탬프 근접 매칭으로 en-ko 세그먼트를 정렬한다 (매칭 실패 세그먼트만 AI 번역 보충).
- 수기 입력에서 영/한 모두 제공된 경우: 문장 수가 맞으면 순서 매칭, 다르면 AI 정렬 요청.

## 단계 4: 학습 항목 4종 추출 (핵심)

### 추출 정책

| 타입 | 정의 | 추출 기준 | 목표 개수/콘텐츠 |
|------|------|-----------|------------------|
| word (레벨 1) | 중요 단어 | 주제 이해에 중요 + 중급 이상 난이도 | 10-30 |
| idiom (레벨 2) | 핵심 숙어/구동사 | 관용 표현, phrasal verb, collocation | 5-15 |
| pattern (레벨 3) | 자주 반복되는 문형 | 스크립트에 2회 이상 등장하거나 범용성 높은 패턴 | 3-10 |
| sentence (레벨 4) | 통암기 가치가 있는 문장 | 완결성 + 실용성 + 패턴/단어를 포함하는 대표 문장 | 5-15 |

### 쉬운 표현 제외 (2중 필터)

1. **프롬프트 필터**: "CEFR A1 수준의 기초 표현(thank you, sorry, got it, hello 등 인사/맞장구/기초 어휘)은 제외"를 명시하고, 각 항목에 `difficulty_hint`(basic/intermediate/advanced)를 자기 평가시킴.
2. **코드 필터**: 응답 후처리에서 `difficulty_hint=basic` 제거 + 저장소 내 기초 어휘 스톱리스트(NGSL 상위 500어 기반, `backend/app/data/easy_words.txt`)와 대조해 word 타입을 2차 제거. 숙어/패턴/문장은 스톱리스트 미적용(구성 단어가 쉬워도 표현 자체는 가치 있음 — 예: "get it over with").

### 프롬프트 설계 (요지)

- 입력: 영/한 세그먼트 전체 (긴 영상은 8,000단어 단위 청크 분할, 청크별 추출 후 병합).
- 출력: JSON 스키마 강제 (Claude structured output / tool use):

```json
{
  "words":     [{"en": "...", "ko": "...", "difficulty": "...", "segment_seq": 12}],
  "idioms":    [{"en": "...", "ko": "...", "difficulty": "...", "segment_seq": 3}],
  "patterns":  [{"template": "It takes ___ to ...", "en_example": "...", "ko": "...", "segment_seq": 7}],
  "sentences": [{"en": "...", "ko": "...", "thinking_ko": "그 나무가 있다, 저기에", "segment_seq": 21}]
}
```

- `thinking_ko`(영어식 사고)는 **문장 타입 필수 생성**: 영어 어순 그대로 직역한 한국어 (레벨 4 퀴즈의 괄호 힌트). 예: "There is a tree over there" → "있다, 나무가, 저기에".
- `segment_seq`로 출처 문장을 지정 → `item_occurrences`에 문맥 저장.

### 저장 + 전역 중복 제거

```
각 항목:
  normalized_key = lower(trim(공백 정규화(en_text)))   # pattern은 template 기준
  learning_items에 (item_type, normalized_key) upsert
    ├─ 신규 → INSERT (review_status=pending)
    └─ 기존 → 항목 재사용 (이미 approved면 그대로 학습 풀 유지)
  item_occurrences에 (item, content, segment) 연결 INSERT
```

같은 단어가 여러 영상에 나와도 항목/카드는 1개, 출처 문맥만 늘어난다.

### 검수 게이트

추출 직후 `review_status=pending` — 관리자가 백오피스에서 승인/수정/제외해야 학습 풀에 편입된다(approved). 상세: [backoffice.md](backoffice.md). 일괄 승인 버튼 제공(콘텐츠 단위).

## API

| 메서드/경로 | 설명 |
|-------------|------|
| POST `/api/admin/contents` | `{source, url?}` 또는 `{source, title, script_en, script_ko?}` → 202 |
| GET `/api/admin/contents` | 목록 + 상태 (페이지네이션) |
| GET `/api/admin/contents/{id}` | 상세: 세그먼트, 추출 항목, job 로그 |
| POST `/api/admin/contents/{id}/retry` | 실패 단계부터 재실행 |
| DELETE `/api/admin/contents/{id}` | 콘텐츠 삭제 (고아 정리는 다른 출처 없고 **연습 기록도 없는** 항목만) |

## 워커 실행 모델

- FastAPI 프로세스 내 asyncio 백그라운드 태스크 큐 (콘텐츠당 1 태스크, 동시 2개 제한 — API 레이트/서버 부하 보호).
- 컨테이너 재시작 시 `status=extracting`인 콘텐츠는 기동 훅에서 pending으로 되돌려 재큐잉 (멱등: 단계별 done 기록은 건너뜀).
- 별도 큐 인프라(Celery/Redis)는 규모상 도입하지 않음 — 필요 시점에 교체 가능하도록 서비스 레이어 분리.

## 비용/한도 추정

- 20분 영상 ≈ 3,000단어 ≈ 입력 4K 토큰 x (번역 1회 + 추출 1회) + 출력 ~3K 토큰 → Sonnet 기준 콘텐츠당 수십 원 수준.
- 유튜브 자막 API는 비공식 — **클라우드 서버 IP는 실제로 차단됨** (2026-07-11 실측: youtube-transcript-api RequestBlocked + yt-dlp bot check). 대응 2단:
  - **로컬 자막 수집기 (기본, 무비용)**: 차단 시 콘텐츠는 실패가 아닌 "자막 준비 중"(status=pending) 상태로 대기하고, transcript 잡은 `failed` 로 기록된다 — 대기 목록 노출 조건이므로 `running` 방치 금지 (2026-07-15 교착 실측). 집 IP를 가진 로컬 머신에서 `scripts/transcript_agent.py` 가 `/api/agent/pending-transcripts`(pending 콘텐츠 + failed transcript 잡 + 세그먼트 없음)를 폴링해 자막을 대신 수집·제출(`X-Agent-Token` 인증)하면 서버가 번역/추출을 이어서 진행. 영어 자막이 확정적으로 없는 영상은 수집기가 `/api/agent/transcripts/{id}/missing` 으로 보고 → 콘텐츠 실패 종결(사용자에게 사유 표시, 재시도 시 재수집). 사용자는 "대기 → 완료" 자동 전환을 본다 (5초 폴링 UI)
  - **프록시 (규모 확장 시)**: `WEBSHARE_PROXY_USERNAME/PASSWORD` (residential) 또는 `YT_PROXY_URL` 설정 시 서버가 직접 수집 — 수집기 없이 동작
