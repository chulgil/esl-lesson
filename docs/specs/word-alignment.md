# 스펙: 단어 단위 정렬 (forced alignment)

> 최종 수정: 2026-07-22

유튜브 자막 문장의 **단어별 시각(start/end)** 을 오디오 정렬로 확보해, 구간 반복(A-B 루프)이 단어 중간에서 잘리거나 옆 문장까지 넘치는 문제를 없애고, 단어 단위 반복/하이라이트를 제공한다. [content-pipeline.md](content-pipeline.md) 단계 2(자막 추출)를 확장한다.

## 배경: 왜 필요한가

현재 문장 경계 시각은 실제 단어 타임스탬프가 아니라 **문자 개수 비율로 보간한 추정값**이다 (`youtube.py` `_time_at`). 말 속도가 글자당 균일하지 않아 경계가 자주 어긋난다:

- 루프가 문장 첫/끝 단어를 놓치거나 끊음 (단어 중간 절단)
- 앞 문장 end 를 다음 문장 start 로 강제 클램프(`merge_into_sentences`)해, 뒤 문장 시작 오차가 앞 문장 루프를 잘라냄
- 자동 생성 자막(문장부호 없음)은 롤링 겹침이 미처리되어 구간이 겹침
- 재생 위치와 자막 표시 어긋남

근본 해결은 오디오에 **실제 단어 시각을 정렬**하는 것이다. 문장 경계는 "첫 단어 start ~ 마지막 단어 end" 로 정확히 파생된다.

## 핵심 원칙: 정렬은 "차단 없는 업그레이드"

정렬은 콘텐츠 준비(`ready`)를 **막지 않는다.** 기존 파이프라인은 그대로 두고(문장은 보간값으로 즉시 `ready`), 로컬 에이전트가 나중에 오디오를 받아 단어 시각을 채워 **정확도만 덧입힌다.**

- 에이전트가 죽어도/정렬이 실패해도 앱은 기존 보간 경계로 정상 동작
- 정렬 성공 시 재추출·재번역 없이 경계만 정밀해짐
- 기존 자막 수집기와 동일한 신뢰 모델 (로컬 IP 대행)

## 실행 위치 제약 (결정)

서버(클라우드 IP)는 유튜브 자막·오디오 다운로드가 모두 차단된다 (content-pipeline.md 비용/한도 참조). Forced alignment 는 **오디오 파형**이 필요하므로, 정렬은 반드시 **집 IP 를 가진 로컬 Mac 에이전트**에서 수행한다. 따라서 `align` 단계는 서버 파이프라인(`run_pipeline`)에 넣지 않고 **에이전트 전용**으로 둔다. 서버는 대기/완료/실패 상태 추적만 한다.

## 데이터 모델

### transcript_segments.words (JSONB, nullable)

세그먼트에 단어 시각 블롭을 추가한다.

```json
words: [
  { "w": "hello", "s": 1230, "e": 1520 },
  { "w": "world", "s": 1520, "e": 1880 }
]
```

- `s`/`e` = 영상 절대 시각(ms). 세그먼트 상대 아님.
- **별도 테이블이 아닌 세그먼트 JSONB 컬럼** 채택 (사용자 결정, 2026-07-22):
  - 단어 시각은 집계 대상이 아니라 **세그먼트와 함께 통째로 읽는 재생용 블롭** (DB 감사 원칙 "집계=정규 테이블 승격" 의 예외)
  - 콘텐츠당 수천 행 폭증 회피, 라이브러리 API 페이로드에 자연 동봉
- `words IS NULL` = 미정렬 → 프론트는 기존 보간 경계로 폴백.
- 정렬 성공 시 세그먼트 `start_ms = words[0].s`, `end_ms = words[-1].e` 로 재계산.

### extraction_jobs.step 에 'align' 추가

CheckConstraint 에 `align` 추가. `run_pipeline` STEPS 루프에는 넣지 않음(에이전트 전용). 대기열/실패 추적 용도로만 사용.

### 마이그레이션

- `transcript_segments.words` JSONB nullable 컬럼 추가
- `extraction_jobs` step CheckConstraint 에 `align` 확장

## 파이프라인 흐름

```
[기존] 로컬 자막 수집 → 서버 문장 병합(보간) → translate → extract → ready
[신규] ready + 세그먼트 존재 → 정렬 대기열 노출
       → 에이전트: 오디오 다운로드(yt-dlp) → stable-ts align → 단어 시각
       → 서버 제출 → 세그먼트 시각 재계산 + words 저장 → align 잡 done
```

기존 콘텐츠는 전부 `words IS NULL` 이므로 자동으로 정렬 대기열에 편입된다 (별도 백필 트리거 불필요, 사용자 결정: 전부 자동 백필).

## 서버 엔드포인트 (backend/app/api/agent.py)

기존 `X-Agent-Token` 인증·패턴을 그대로 재사용한다.

| 메서드/경로 | 역할 |
|---|---|
| GET `/api/agent/pending-alignments` | 정렬 대기 콘텐츠 목록: `status=ready` + 세그먼트 존재 + 아직 정렬 안 됨(align 잡이 done/failed 아님). 응답에 세그먼트 `{seq, en_text}` 동봉 (에이전트가 정렬 대상 텍스트로 사용). limit 20 |
| POST `/api/agent/transcripts/{id}/alignment` | 에이전트가 `{alignments: {seq: [{w,s,e}]}}` 제출 → 세그먼트별 `words` 저장 + `start_ms/end_ms` 재계산 → align 잡 done → 202 |
| POST `/api/agent/transcripts/{id}/alignment/failed` | 오디오 항구 불가(비공개/삭제 등) 보고 → align 잡 failed (대기열 제외). 관리자 재시도로 복구 |

### 제출 처리 규칙

- **멱등**: 이미 정렬됨(모든 세그먼트 words 존재 또는 align 잡 done)이면 skip.
- 콘텐츠에 속한 seq 만 갱신, 모르는 seq 는 무시.
- 각 세그먼트: `words` 저장, `start_ms=words[0].s`, `end_ms=max(start_ms, words[-1].e)`.
- **인접 세그먼트 단조 안전 클램프**(경미): 정렬 오차로 겹칠 경우 `prev.end_ms = min(prev.end_ms, cur.start_ms)` 유지.

### 대기열 쿼리

`pending_transcripts` 와 동형. 조건: `source='youtube'`, `status='ready'`, 세그먼트 존재, align 잡이 `done`/`failed` 상태가 아님(잡 없거나 pending/running). limit 20, id 순.

## 로컬 에이전트 정렬 모듈

기존 launchd 상주 프로세스(`com.esl.transcript-agent` → `backend/scripts/transcript_agent.py`)를 **확장**한다 (별도 launchd·토큰 불필요). 매 폴링 주기에 `pending-transcripts`(기존) + `pending-alignments`(신규) 를 함께 처리.

### 신규 로컬 의존성

- `yt-dlp` — 오디오 다운로드 (집 IP 라 동작)
- `ffmpeg` — 오디오 변환 (brew install ffmpeg)
- `stable-ts` — 정렬 (torch 포함, 첫 설치 시 모델 다운로드)

torch/stable-ts 는 **정렬 작업이 있을 때만 지연 임포트** → 유휴 시 메모리 부담 없음.

### 모듈 구조 (backend/scripts/lib/align.py)

```
class Word(TypedDict): w: str; s: int; e: int

class Aligner(Protocol):
    def align(self, audio_path: str, segments: list[tuple[int, str]]) -> dict[int, list[Word]]: ...

class StableTsAligner:               # 기본 구현 (교체 가능)
    - 모델 1회 로드 캐시 (기본 base.en, ESL_ALIGN_MODEL 로 변경)
    - full-pass: model.align(audio, 전체_세그먼트_텍스트, language='en')
    - 정렬된 단어를 세그먼트 seq 로 재분배

def download_audio(video_id: str) -> str:   # yt-dlp bestaudio → ffmpeg m4a, 임시 디렉토리, 사용 후 정리
```

- 정렬 엔진은 `Aligner` 인터페이스로 분리 → 향후 WhisperX 등으로 교체 가능.
- **텍스트는 유튜브 자막 그대로 유지**하고 정렬만 한다 (재-ASR 로 텍스트를 바꾸면 이미 추출된 학습 항목과 어긋남).
- 콘텐츠당 오디오 1회 다운로드 → 1패스 정렬.

### 단어 → 세그먼트 재분배 (토큰화 차이 대응)

정렬기의 단어 분할(축약형 `don't`, 문장부호 부착 등)이 세그먼트 원문 공백 분할과 다를 수 있다. 단순 단어 수 매칭 대신 **텍스트 재구성 기준**으로 매핑한다:

- 정렬된 단어를 순서대로 소비하며 각 세그먼트의 `en_text` 를 (공백·문장부호 정규화 후) 복원될 때까지 채운다.
- 정규화 후 문자열이 일치하면 그 구간의 단어들을 해당 seq 에 귀속.
- 불일치·소진 등 매칭 실패 시 해당 콘텐츠는 정렬 결과를 버리고 폴백 유지(부분 오정렬 방지) — best-effort 원칙.

## 프론트엔드

라이브러리 상세(`frontend/src/app/library/[id]/page.tsx`)가 1차 무대. `LibraryDetail` 세그먼트 타입에 `words?: {w,s,e}[]` 추가.

### 현재 단어 하이라이트

- 기존 100ms 폴링(문장 동기·A-B 루프 감시) 안에서 활성 세그먼트의 단어 중 `w.s <= now < w.e` 를 찾아 강조.
- 문장은 단어 span 으로 렌더(`words` 있을 때). 없으면 기존 평문 + 문장 루프로 폴백.

### 단어 탭 → 그 단어만 반복

- 단어 span 클릭 → `rangeRef = { start: w.s/1000, end: max(w.e, w.s+400)/1000 }` (단어가 짧아 최소 길이 400ms 보장) 로 A-B 루프. 기존 루프 메커니즘 재사용.
- 시각적 어포던스(클릭 가능 표시) 제공.

### 기존 폴백 유지

`_time_at` 보간, `merge_into_sentences` 클램프, `SegmentPlayer` 8초 상한, `playSegment` 최소 1초 — **미정렬 콘텐츠 폴백용으로 유지**. 정렬되면 정확한 경계를 쓰므로 이 보정들은 거의 발동하지 않는다.

## 에러 처리 · 백필 롤아웃

- 정렬은 **best-effort**: 실패해도 `ready` 불변, 앱 정상.
- 실패 구분:
  - 이 영상 오디오 항구 불가(비공개/삭제) → `.../alignment/failed` 보고로 대기열 제외
  - 도구 미설치/네트워크 일시 오류 → 콘텐츠 실패 처리하지 않고 다음 주기 재시도 (+ 명확한 셋업 로그: brew/yt-dlp 안내)
- 백필: `pending-alignments` limit 20 배치로 시간에 걸쳐 소진. 진행 로그. 기존 콘텐츠 전부 자동 편입.
- 부분 실패(일부 세그먼트만 정렬)는 없음 — 콘텐츠 단위 1패스로 전 세그먼트를 함께 갱신.

## 테스트

- 백엔드
  - alignment 제출: words 저장·경계 재계산·멱등 skip·미지 seq 무시·align 잡 done
  - `pending-alignments` 쿼리: ready+세그먼트+미정렬만, 정렬됨/실패 제외
  - 경계 파생 헬퍼: words → 세그먼트 start/end, 단조 안전 클램프
  - 마이그레이션 스모크: words 컬럼, align 제약
- 에이전트 (aligner·오디오 다운로드 목킹)
  - 단어 → 세그먼트 재분배 로직 (단어 수 기준 분할)
- 프론트
  - 단어 span 렌더 / 활성 단어 선택(now 기준) / 단어 탭 루프 범위 / `words` null 폴백
- 레드-그린: "words 있는 세그먼트 → 루프 범위가 실단어 경계" 회귀 (정렬 전엔 부정확했음 확인)

## 범위 밖 / 후속

- 학습 세션 `InsightSheet` 단어 클릭을 TTS → 유튜브 단어 루프로 전환 (이번 범위 밖, 후속)
- 정렬 엔진 WhisperX 교체 (인터페이스는 준비, 필요 시)
- 단어 시각 기반 노래방식 전체 자막 카라오케 렌더 (범위 밖)
