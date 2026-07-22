# 단어 단위 정렬 (forced alignment) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 유튜브 자막 문장의 단어별 시각을 오디오 정렬로 확보해 구간 반복 정확도를 높이고, 단어 단위 반복/하이라이트를 제공한다.

**Architecture:** 정렬은 로컬 Mac 자막 수집기(집 IP)에서 stable-ts 로 수행한다. 서버는 유튜브 오디오가 차단되므로 정렬을 못 한다 — `align` 은 에이전트 전용 단계이며, 콘텐츠 `ready` 를 막지 않는 best-effort 업그레이드다. 단어 시각은 `transcript_segments.words`(JSONB) 에 저장하고, 세그먼트 경계는 단어 시각에서 파생한다. 프론트는 라이브러리 상세에서 현재 단어 하이라이트 + 단어 탭 반복을 제공하고, `words` 없으면 기존 보간 경계로 폴백한다.

**Tech Stack:** FastAPI + SQLAlchemy 2 + Alembic (백엔드), Python 3.12 + uv, stable-ts(정렬, 옵션 의존성) + yt-dlp + ffmpeg(로컬), Next.js 15 + TypeScript (프론트).

**Spec:** [docs/specs/word-alignment.md](../specs/word-alignment.md)

## Global Constraints

- Python `>=3.12`. ruff line-length 100, lint select `E,F,I,UP,B`. 커밋 전 `uv run ruff check .` + `uv run ruff format .`.
- 커밋 메시지: 한글 Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- **이모지/유니코드 심볼 금지** (코드·주석·커밋·문서 전부). ASCII 만.
- **불변성**: 새 객체 생성, 원본 변형 금지. (단, SQLAlchemy ORM 인스턴스 속성 갱신은 표준 패턴이므로 허용)
- **서버에 torch/stable-ts 를 설치하지 않는다** — 2GB 서버 OOM 방지. stable-ts 는 `[dependency-groups] align` 옵션 그룹, 에이전트에서 지연 임포트.
- **정렬은 best-effort**: 실패해도 `content.status` 불변, 앱은 기존 보간 경계로 정상 동작.
- **텍스트는 유튜브 자막 그대로 유지**하고 정렬만 한다 (재-ASR 금지 — 추출된 학습 항목과 어긋남).
- 백엔드 테스트: `cd backend && uv run pytest`. asyncio_mode=auto, 인메모리 sqlite 픽스처(`tests/conftest.py`).
- 프론트: 유닛 테스트 러너 없음 — 검증은 `npm run lint` + `npm run build`(타입체크) + 헤드리스 스크린샷(라이브러리 상세).
- alembic 현재 head: `a9b0c1d2e3f4` (새 마이그레이션 down_revision).

---

## File Structure

**백엔드 (서버, TDD)**
- Modify `backend/app/models/content.py` — `TranscriptSegment.words` 컬럼 + `ExtractionJob` step 제약에 `align` 추가
- Create `backend/alembic/versions/b1c2d3e4a5f6_add_segment_words_and_align_step.py` — 마이그레이션
- Create `backend/app/services/alignment.py` — `apply_alignment()` 순수 헬퍼(경계 재계산·클램프)
- Modify `backend/app/api/agent.py` — `pending-alignments` / `alignment` / `alignment/failed` 엔드포인트
- Modify `backend/app/api/contents.py:122` — 라이브러리 상세에 `words` 노출
- Create `backend/tests/test_alignment_service.py` — apply_alignment 유닛
- Create `backend/tests/test_agent_alignment.py` — 엔드포인트
- Modify `backend/tests/test_my_contents.py` 인접 — 라이브러리 상세 words 노출 테스트(신규 파일 `test_contents_detail.py`)

**로컬 에이전트 (TDD 순수 로직 + 목킹 통합)**
- Create `backend/scripts/__init__.py`, `backend/scripts/lib/__init__.py`
- Create `backend/scripts/lib/align.py` — `remap_result_to_segments()`(순수) + `StableTsAligner` + `download_audio()`
- Modify `backend/scripts/transcript_agent.py` — 정렬 패스 추가 + sys.path 션트
- Create `backend/tests/test_align_lib.py` — remap 순수 로직 + 정렬 패스(목킹)
- Modify `backend/pyproject.toml` — `[dependency-groups] align`

**프론트 (build/lint/헤드리스 검증)**
- Modify `frontend/src/lib/study-api.ts` — LibraryDetail 세그먼트에 `words?`
- Create `frontend/src/components/media/TranscriptWords.tsx` — 단어 span 렌더·활성 하이라이트·탭
- Modify `frontend/src/app/library/[id]/page.tsx` — 통합(nowMs 추적·단어 탭 반복)

---

## Task 1: DB 모델 + 마이그레이션

**Files:**
- Modify: `backend/app/models/content.py`
- Create: `backend/alembic/versions/b1c2d3e4a5f6_add_segment_words_and_align_step.py`
- Test: `backend/tests/test_alignment_service.py` (모델 저장/제약 확인 포함)

**Interfaces:**
- Produces: `TranscriptSegment.words: list | None` (JSON), `ExtractionJob.step` 에 `'align'` 허용.

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_alignment_service.py`

```python
"""단어 정렬 저장/경계 재계산 (docs/specs/word-alignment.md)."""

from app.models import ExtractionJob, TranscriptSegment


async def test_segment_stores_words_json(db_session):
    seg = TranscriptSegment(
        content_id=1, seq=0, start_ms=0, end_ms=2000, en_text="Hello world."
    )
    seg.words = [{"w": "Hello", "s": 100, "e": 500}, {"w": "world", "s": 500, "e": 900}]
    db_session.add(seg)
    await db_session.commit()
    await db_session.refresh(seg)
    assert seg.words[0]["w"] == "Hello"


async def test_extraction_job_accepts_align_step(db_session):
    job = ExtractionJob(content_id=1, step="align", status="pending")
    db_session.add(job)
    await db_session.commit()  # CHECK 제약 통과해야 함
    assert job.step == "align"
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_alignment_service.py -v`
Expected: FAIL — `words` 속성 없음(AttributeError) + `align` step CHECK 위반(IntegrityError)

- [ ] **Step 3: 모델 수정** — `backend/app/models/content.py`

`TranscriptSegment` 에 컬럼 추가 (`ko_text` 아래):

```python
    ko_text: Mapped[str | None] = mapped_column(Text)
    # 단어별 시각 [{"w","s","e"}] — 로컬 에이전트 정렬 결과 (docs/specs/word-alignment.md).
    # NULL = 미정렬 → 프론트는 보간 경계로 폴백
    words: Mapped[list | None] = mapped_column(JsonDict, nullable=True)
```

`ExtractionJob.__table_args__` 의 step CHECK 에 `align` 추가:

```python
        CheckConstraint(
            "step IN ('metadata','transcript','translate','extract','embed','align')",
            name="ck_jobs_step",
        ),
```

(`JsonDict` 는 이미 `from app.models.types import JsonDict` 로 import 됨 — 확인만.)

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_alignment_service.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 마이그레이션 작성** — `backend/alembic/versions/b1c2d3e4a5f6_add_segment_words_and_align_step.py`

```python
"""단어 정렬 — transcript_segments.words + extraction_jobs align 단계.

Revision ID: b1c2d3e4a5f6
Revises: a9b0c1d2e3f4
Create Date: 2026-07-22
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b1c2d3e4a5f6"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None

_STEPS_OLD = "step IN ('metadata','transcript','translate','extract','embed')"
_STEPS_NEW = "step IN ('metadata','transcript','translate','extract','embed','align')"


def upgrade() -> None:
    op.add_column(
        "transcript_segments",
        sa.Column("words", postgresql.JSONB(), nullable=True),
    )
    op.drop_constraint("ck_jobs_step", "extraction_jobs", type_="check")
    op.create_check_constraint("ck_jobs_step", "extraction_jobs", _STEPS_NEW)


def downgrade() -> None:
    op.drop_constraint("ck_jobs_step", "extraction_jobs", type_="check")
    op.create_check_constraint("ck_jobs_step", "extraction_jobs", _STEPS_OLD)
    op.drop_column("transcript_segments", "words")
```

- [ ] **Step 6: head 단일 확인**

Run: `cd backend && uv run alembic heads`
Expected: `b1c2d3e4a5f6 (head)` 한 줄 (분기 없음)

- [ ] **Step 7: 전체 테스트 그린 + 커밋**

Run: `cd backend && uv run ruff check . && uv run ruff format . && uv run pytest -q`
Expected: 전부 통과

```bash
git add backend/app/models/content.py backend/alembic/versions/b1c2d3e4a5f6_add_segment_words_and_align_step.py backend/tests/test_alignment_service.py
git commit -m "feat: transcript_segments.words 컬럼 + align 단계 추가"
```

---

## Task 2: 정렬 적용 서비스 (경계 재계산)

**Files:**
- Create: `backend/app/services/alignment.py`
- Test: `backend/tests/test_alignment_service.py` (추가)

**Interfaces:**
- Produces: `apply_alignment(segments: list[TranscriptSegment], alignments: dict[int, list[dict]]) -> int` — 각 세그먼트 `words` 저장 + `start_ms=words[0]["s"]`, `end_ms=max(start, words[-1]["e"])`, 인접 단조 클램프. 갱신된 세그먼트 수 반환. 모르는 seq·빈 words 무시.

- [ ] **Step 1: 실패 테스트 추가** — `backend/tests/test_alignment_service.py` 하단에

```python
from app.services.alignment import apply_alignment


def _seg(seq, start, end, text="x"):
    return TranscriptSegment(content_id=1, seq=seq, start_ms=start, end_ms=end, en_text=text)


def test_apply_alignment_recomputes_bounds_and_stores_words():
    segs = [_seg(0, 0, 5000), _seg(1, 5000, 9000)]
    alignments = {
        0: [{"w": "Hi", "s": 120, "e": 700}, {"w": "there", "s": 700, "e": 1400}],
        1: [{"w": "Bye", "s": 5200, "e": 5900}],
    }
    updated = apply_alignment(segs, alignments)
    assert updated == 2
    assert segs[0].start_ms == 120 and segs[0].end_ms == 1400
    assert segs[1].start_ms == 5200 and segs[1].end_ms == 5900
    assert segs[0].words[1]["w"] == "there"


def test_apply_alignment_clamps_overlap_between_neighbors():
    segs = [_seg(0, 0, 5000), _seg(1, 5000, 9000)]
    # seg1 시작이 seg0 끝보다 앞 — 겹침 → seg0.end 를 seg1.start 로 절단
    alignments = {
        0: [{"w": "a", "s": 0, "e": 3000}],
        1: [{"w": "b", "s": 2500, "e": 6000}],
    }
    apply_alignment(segs, alignments)
    assert segs[0].end_ms == 2500


def test_apply_alignment_ignores_unknown_seq_and_empty():
    segs = [_seg(0, 0, 5000)]
    updated = apply_alignment(segs, {9: [{"w": "x", "s": 0, "e": 1}], 0: []})
    assert updated == 0
    assert segs[0].words is None
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_alignment_service.py -v -k apply_alignment`
Expected: FAIL — `app.services.alignment` 없음(ImportError)

- [ ] **Step 3: 구현** — `backend/app/services/alignment.py`

```python
"""단어 정렬 적용 — words 저장 + 세그먼트 경계 재계산 (docs/specs/word-alignment.md)."""

from app.models import TranscriptSegment


def apply_alignment(
    segments: list[TranscriptSegment], alignments: dict[int, list[dict]]
) -> int:
    """seq→단어시각 을 세그먼트에 적용. start/end 를 단어 시각에서 파생하고
    인접 세그먼트 겹침을 단조 클램프한다. 갱신된 세그먼트 수 반환."""
    by_seq = {s.seq: s for s in segments}
    updated = 0
    for seq, words in alignments.items():
        seg = by_seq.get(seq)
        if seg is None or not words:
            continue
        seg.words = [{"w": w["w"], "s": int(w["s"]), "e": int(w["e"])} for w in words]
        seg.start_ms = seg.words[0]["s"]
        seg.end_ms = max(seg.start_ms, seg.words[-1]["e"])
        updated += 1

    ordered = sorted(segments, key=lambda s: s.seq)
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        if prev.words and cur.words and prev.start_ms is not None:
            prev.end_ms = max(prev.start_ms, min(prev.end_ms, cur.start_ms))
    return updated
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_alignment_service.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
cd backend && uv run ruff check . && uv run ruff format .
git add backend/app/services/alignment.py backend/tests/test_alignment_service.py
git commit -m "feat: 정렬 적용 서비스 apply_alignment (경계 재계산·클램프)"
```

---

## Task 3: 에이전트 정렬 엔드포인트

**Files:**
- Modify: `backend/app/api/agent.py`
- Test: `backend/tests/test_agent_alignment.py`

**Interfaces:**
- Consumes: `apply_alignment` (Task 2), `X-Agent-Token` 인증(`require_agent_token`, 기존).
- Produces:
  - `GET /api/agent/pending-alignments` → `{"items": [{"content_id", "youtube_video_id", "segments": [{"seq","en_text"}]}]}`
  - `POST /api/agent/transcripts/{id}/alignment` body `{"alignments": {seq: [{"w","s","e"}]}}` → 202 `{"content_id","aligned"}`
  - `POST /api/agent/transcripts/{id}/alignment/failed` → `{"content_id","status":"failed"}`

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_agent_alignment.py`

```python
"""에이전트 정렬 엔드포인트 (docs/specs/word-alignment.md)."""

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import Content, ExtractionJob, TranscriptSegment

AGENT_HEADERS = {"X-Agent-Token": "test-agent-token"}


@pytest.fixture(autouse=True)
def agent_token_env(monkeypatch):
    monkeypatch.setenv("AGENT_TOKEN", "test-agent-token")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _ready_content(db, *, video="dQw4w9WgXcQ"):
    content = Content(source="youtube", youtube_video_id=video, title="T", status="ready")
    db.add(content)
    await db.flush()
    db.add(TranscriptSegment(content_id=content.id, seq=0, start_ms=0, end_ms=5000, en_text="Hi there."))
    db.add(TranscriptSegment(content_id=content.id, seq=1, start_ms=5000, end_ms=9000, en_text="Bye now."))
    await db.commit()
    return content


async def test_pending_alignments_lists_ready_unaligned(client, db_session):
    content = await _ready_content(db_session)
    listed = (await client.get("/api/agent/pending-alignments", headers=AGENT_HEADERS)).json()
    assert listed["items"][0]["content_id"] == content.id
    assert listed["items"][0]["segments"] == [
        {"seq": 0, "en_text": "Hi there."},
        {"seq": 1, "en_text": "Bye now."},
    ]


async def test_submit_alignment_stores_words_and_recomputes(client, db_session):
    content = await _ready_content(db_session)
    res = await client.post(
        f"/api/agent/transcripts/{content.id}/alignment",
        headers=AGENT_HEADERS,
        json={"alignments": {
            "0": [{"w": "Hi", "s": 120, "e": 700}, {"w": "there", "s": 700, "e": 1400}],
            "1": [{"w": "Bye", "s": 5200, "e": 5900}, {"w": "now", "s": 5900, "e": 6300}],
        }},
    )
    assert res.status_code == 202
    assert res.json()["aligned"] == 2

    segs = (await db_session.execute(
        select(TranscriptSegment).where(TranscriptSegment.content_id == content.id)
        .order_by(TranscriptSegment.seq)
    )).scalars().all()
    assert segs[0].start_ms == 120 and segs[0].end_ms == 1400
    assert segs[0].words[0]["w"] == "Hi"

    job = (await db_session.execute(
        select(ExtractionJob).where(
            ExtractionJob.content_id == content.id, ExtractionJob.step == "align"
        )
    )).scalar_one()
    assert job.status == "done"

    # 정렬됨 → 대기 목록에서 사라짐
    listed = (await client.get("/api/agent/pending-alignments", headers=AGENT_HEADERS)).json()
    assert listed["items"] == []


async def test_submit_alignment_idempotent(client, db_session):
    content = await _ready_content(db_session)
    body = {"alignments": {"0": [{"w": "Hi", "s": 1, "e": 2}]}}
    await client.post(f"/api/agent/transcripts/{content.id}/alignment", headers=AGENT_HEADERS, json=body)
    dup = await client.post(f"/api/agent/transcripts/{content.id}/alignment", headers=AGENT_HEADERS, json=body)
    assert dup.json().get("skipped") is True


async def test_alignment_failed_drops_from_queue(client, db_session):
    content = await _ready_content(db_session)
    res = await client.post(
        f"/api/agent/transcripts/{content.id}/alignment/failed", headers=AGENT_HEADERS
    )
    assert res.status_code == 200
    listed = (await client.get("/api/agent/pending-alignments", headers=AGENT_HEADERS)).json()
    assert listed["items"] == []


async def test_alignment_requires_token(client, db_session):
    assert (await client.get("/api/agent/pending-alignments")).status_code == 401
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_agent_alignment.py -v`
Expected: FAIL — 404/405 (엔드포인트 없음)

- [ ] **Step 3: 구현** — `backend/app/api/agent.py`

상단 import 에 추가:

```python
from app.services.alignment import apply_alignment
```

파일 하단에 헬퍼 + 엔드포인트 추가:

```python
async def _get_or_create_job(db: AsyncSession, content_id: int, step: str) -> ExtractionJob:
    job = (
        await db.execute(
            select(ExtractionJob).where(
                ExtractionJob.content_id == content_id, ExtractionJob.step == step
            )
        )
    ).scalar_one_or_none()
    if job is None:
        job = ExtractionJob(content_id=content_id, step=step)
        db.add(job)
    return job


@router.get("/pending-alignments", dependencies=[Depends(require_agent_token)])
async def pending_alignments(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """정렬 대기 콘텐츠: ready + 세그먼트 존재 + align 잡이 done/failed 아님."""
    has_segments = exists(
        select(TranscriptSegment.id).where(TranscriptSegment.content_id == Content.id)
    )
    align_settled = exists(
        select(ExtractionJob.id).where(
            ExtractionJob.content_id == Content.id,
            ExtractionJob.step == "align",
            ExtractionJob.status.in_(("done", "failed")),
        )
    )
    rows = (
        (
            await db.execute(
                select(Content)
                .where(
                    Content.source == "youtube",
                    Content.status == "ready",
                    has_segments,
                    ~align_settled,
                )
                .order_by(Content.id)
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    items = []
    for content in rows:
        segs = (
            await db.execute(
                select(TranscriptSegment.seq, TranscriptSegment.en_text)
                .where(TranscriptSegment.content_id == content.id)
                .order_by(TranscriptSegment.seq)
            )
        ).all()
        items.append(
            {
                "content_id": content.id,
                "youtube_video_id": content.youtube_video_id,
                "segments": [{"seq": s.seq, "en_text": s.en_text} for s in segs],
            }
        )
    return {"items": items}


class WordBody(BaseModel):
    w: str
    s: int = Field(ge=0)
    e: int = Field(ge=0)


class AlignmentSubmit(BaseModel):
    alignments: dict[int, list[WordBody]] = Field(min_length=1)


@router.post(
    "/transcripts/{content_id}/alignment",
    dependencies=[Depends(require_agent_token)],
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_alignment(
    content_id: int,
    body: AlignmentSubmit,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    content = await db.get(Content, content_id)
    if content is None or content.source != "youtube":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    job = await _get_or_create_job(db, content_id, "align")
    if job.status == "done":
        return {"content_id": content_id, "skipped": True}

    segments = (
        (
            await db.execute(
                select(TranscriptSegment).where(TranscriptSegment.content_id == content_id)
            )
        )
        .scalars()
        .all()
    )
    alignments = {
        seq: [w.model_dump() for w in words] for seq, words in body.alignments.items()
    }
    aligned = apply_alignment(segments, alignments)

    job.status = "done"
    job.error = None
    job.payload = {"aligned": aligned, "source": "local_agent"}
    await db.commit()
    return {"content_id": content_id, "aligned": aligned}


@router.post(
    "/transcripts/{content_id}/alignment/failed",
    dependencies=[Depends(require_agent_token)],
)
async def report_alignment_failed(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """오디오 항구 불가(비공개/삭제) 보고 → align 잡 failed 로 대기열 제외."""
    content = await db.get(Content, content_id)
    if content is None or content.source != "youtube":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    job = await _get_or_create_job(db, content_id, "align")
    job.status = "failed"
    job.error = "audio unavailable for alignment"
    job.payload = {"source": "local_agent", "reason": "audio_unavailable"}
    await db.commit()
    return {"content_id": content_id, "status": "failed"}
```

(참고: `exists`, `select`, `BaseModel`, `Field`, `TranscriptSegment`, `ExtractionJob` 은 이미 `agent.py` 에 import 되어 있음 — 없으면 추가.)

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_agent_alignment.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
cd backend && uv run ruff check . && uv run ruff format .
git add backend/app/api/agent.py backend/tests/test_agent_alignment.py
git commit -m "feat: 에이전트 정렬 엔드포인트 (대기열·제출·실패보고)"
```

---

## Task 4: 라이브러리 상세에 words 노출

**Files:**
- Modify: `backend/app/api/contents.py:122-131`
- Test: `backend/tests/test_contents_detail.py`

**Interfaces:**
- Produces: `GET /api/contents/{id}` 세그먼트에 `"words"` 필드.

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_contents_detail.py`

```python
"""라이브러리 상세 API 의 단어 시각 노출 (docs/specs/word-alignment.md)."""

from app.models import Content, TranscriptSegment
from tests.test_my_contents import login_as


async def test_library_detail_exposes_words(client, db_session):
    user = await login_as(client, db_session, "u1@example.com")
    content = Content(
        source="youtube", youtube_video_id="vid00000001", title="T",
        visibility="private", status="ready", created_by=user.id,
    )
    db_session.add(content)
    await db_session.flush()
    from app.models import ContentSubscription

    db_session.add(ContentSubscription(content_id=content.id, user_id=user.id))
    seg = TranscriptSegment(
        content_id=content.id, seq=0, start_ms=100, end_ms=1400, en_text="Hi there."
    )
    seg.words = [{"w": "Hi", "s": 100, "e": 700}, {"w": "there", "s": 700, "e": 1400}]
    db_session.add(seg)
    await db_session.commit()

    detail = (await client.get(f"/api/contents/{content.id}")).json()
    assert detail["segments"][0]["words"][1] == {"w": "there", "s": 700, "e": 1400}


async def test_library_detail_words_null_when_unaligned(client, db_session):
    user = await login_as(client, db_session, "u1@example.com")
    content = Content(
        source="youtube", youtube_video_id="vid00000002", title="T",
        visibility="private", status="ready", created_by=user.id,
    )
    db_session.add(content)
    await db_session.flush()
    from app.models import ContentSubscription

    db_session.add(ContentSubscription(content_id=content.id, user_id=user.id))
    db_session.add(
        TranscriptSegment(content_id=content.id, seq=0, start_ms=0, end_ms=1000, en_text="Hi.")
    )
    await db_session.commit()

    detail = (await client.get(f"/api/contents/{content.id}")).json()
    assert detail["segments"][0]["words"] is None
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_contents_detail.py -v`
Expected: FAIL — `KeyError: 'words'`

- [ ] **Step 3: 구현** — `backend/app/api/contents.py` 세그먼트 dict 에 한 줄 추가

```python
        "segments": [
            {
                "seq": s.seq,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "en_text": s.en_text,
                "ko_text": s.ko_text,
                "words": s.words,
            }
            for s in segments
        ],
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_contents_detail.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
cd backend && uv run ruff check . && uv run ruff format .
git add backend/app/api/contents.py backend/tests/test_contents_detail.py
git commit -m "feat: 라이브러리 상세 API 에 단어 시각(words) 노출"
```

---

## Task 5: 에이전트 정렬 라이브러리 (remap 순수 로직 + Aligner)

**Files:**
- Create: `backend/scripts/__init__.py` (빈 파일)
- Create: `backend/scripts/lib/__init__.py` (빈 파일)
- Create: `backend/scripts/lib/align.py`
- Test: `backend/tests/test_align_lib.py`

**Interfaces:**
- Produces:
  - `remap_result_to_segments(result_segments, seg_count) -> dict[int, list[dict]] | None` — stable-ts 결과 세그먼트를 seq→단어시각 으로. 세그먼트 개수 불일치·빈 세그먼트면 `None`(폴백).
  - `StableTsAligner(model_name=None).align(audio_path, segments: list[tuple[int,str]]) -> dict | None`
  - `download_audio(video_id: str) -> str` (오디오 파일 경로)

- [ ] **Step 1: 실패 테스트 작성** — `backend/tests/test_align_lib.py`

```python
"""에이전트 정렬 라이브러리 — remap 순수 로직 (docs/specs/word-alignment.md)."""

from types import SimpleNamespace

from scripts.lib.align import remap_result_to_segments


def _word(text, start, end):
    return SimpleNamespace(word=text, start=start, end=end)


def _seg(words):
    return SimpleNamespace(words=words)


def test_remap_index_maps_when_counts_match():
    result_segments = [
        _seg([_word(" Hi", 0.10, 0.70), _word(" there", 0.70, 1.40)]),
        _seg([_word(" Bye", 5.20, 5.90)]),
    ]
    out = remap_result_to_segments(result_segments, 2)
    assert out == {
        0: [{"w": "Hi", "s": 100, "e": 700}, {"w": "there", "s": 700, "e": 1400}],
        1: [{"w": "Bye", "s": 5200, "e": 5900}],
    }


def test_remap_returns_none_on_count_mismatch():
    result_segments = [_seg([_word("a", 0.0, 0.1)])]
    assert remap_result_to_segments(result_segments, 2) is None


def test_remap_returns_none_when_segment_has_no_words():
    result_segments = [_seg([_word("a", 0.0, 0.1)]), _seg([])]
    assert remap_result_to_segments(result_segments, 2) is None
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_align_lib.py -v`
Expected: FAIL — `scripts.lib.align` 없음(ImportError)

- [ ] **Step 3: 구현** — `backend/scripts/__init__.py` 와 `backend/scripts/lib/__init__.py` 는 빈 파일. `backend/scripts/lib/align.py`:

```python
"""단어 정렬 — stable-ts 로 오디오에 자막 텍스트를 정렬 (docs/specs/word-alignment.md).

서버가 아니라 로컬 Mac 에이전트에서 실행된다. stable-ts/torch 는 지연 임포트.
"""

import os
import subprocess
import tempfile


def remap_result_to_segments(result_segments, seg_count: int) -> dict | None:
    """stable-ts align(original_split=True) 결과를 seq→단어시각 으로 변환.

    입력 텍스트를 세그먼트당 한 줄로 주면 결과 세그먼트가 줄 단위로 나뉘어
    인덱스가 seq 와 일치한다. 개수 불일치/빈 세그먼트는 None(폴백)로 안전 처리.
    """
    if len(result_segments) != seg_count:
        return None
    out: dict[int, list[dict]] = {}
    for seq, rseg in enumerate(result_segments):
        words = []
        for w in rseg.words:
            text = (w.word or "").strip()
            if not text:
                continue
            words.append({"w": text, "s": round(w.start * 1000), "e": round(w.end * 1000)})
        if not words:
            return None
        out[seq] = words
    return out


class StableTsAligner:
    """stable-ts 정렬기. 모델은 최초 사용 시 1회 로드 후 캐시."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or os.environ.get("ESL_ALIGN_MODEL", "base.en")
        self._model = None

    def _load(self):
        if self._model is None:
            import stable_whisper  # 지연 임포트 (torch)

            self._model = stable_whisper.load_model(self._model_name)
        return self._model

    def align(self, audio_path: str, segments: list[tuple[int, str]]) -> dict | None:
        model = self._load()
        text = "\n".join(en for _, en in segments)
        result = model.align(audio_path, text, language="en", original_split=True)
        return remap_result_to_segments(result.segments, len(segments))


def download_audio(video_id: str) -> str:
    """yt-dlp 로 bestaudio 를 임시 디렉토리에 내려받아 경로 반환 (ffmpeg 필요).

    호출측이 os.path.dirname(경로) 를 정리한다.
    """
    tmpdir = tempfile.mkdtemp(prefix="esl-align-")
    subprocess.run(
        [
            "yt-dlp", "-f", "bestaudio", "--extract-audio", "--audio-format", "m4a",
            "-o", os.path.join(tmpdir, "%(id)s.%(ext)s"),
            f"https://www.youtube.com/watch?v={video_id}",
        ],
        check=True,
        capture_output=True,
    )
    return os.path.join(tmpdir, f"{video_id}.m4a")
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_align_lib.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 옵션 의존성 그룹 추가** — `backend/pyproject.toml` 의 `[dependency-groups]` 에 추가

```toml
[dependency-groups]
dev = [
    "aiosqlite>=0.22.1",
    "pytest>=9.1.1",
    "pytest-asyncio>=1.4.0",
    "ruff>=0.15.21",
]
align = [
    "stable-ts>=2.17.0",
]
```

(주의: 서버 배포는 이 그룹을 설치하지 않는다. 로컬 에이전트만 `uv sync --group align`.)

- [ ] **Step 6: 커밋**

```bash
cd backend && uv run ruff check . && uv run ruff format .
git add backend/scripts/__init__.py backend/scripts/lib/__init__.py backend/scripts/lib/align.py backend/tests/test_align_lib.py backend/pyproject.toml
git commit -m "feat: 에이전트 정렬 라이브러리(stable-ts) + remap 로직"
```

---

## Task 6: 에이전트 루프에 정렬 패스 통합

**Files:**
- Modify: `backend/scripts/transcript_agent.py`
- Test: `backend/tests/test_align_lib.py` (추가)

**Interfaces:**
- Consumes: `remap`/`StableTsAligner`/`download_audio` (Task 5), 서버 정렬 엔드포인트 (Task 3).
- Produces: `process_alignments_once(client, aligner=None, downloader=None) -> int` — 대기열 처리, 정렬 제출/실패보고. `main()` 루프에서 매 주기 호출.

- [ ] **Step 1: 실패 테스트 추가** — `backend/tests/test_align_lib.py` 하단

```python
class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


class _FakeClient:
    """pending-alignments 1건 반환 후, 이후 호출 기록."""

    def __init__(self, items):
        self._items = items
        self.posts = []

    def get(self, url):
        return _FakeResp(payload={"items": self._items})

    def post(self, url, json=None):
        self.posts.append((url, json))
        return _FakeResp(status_code=202, payload={"aligned": len(json["alignments"]) if json else 0})


def test_process_alignments_submits_mapped_words(monkeypatch):
    from scripts import transcript_agent

    items = [{
        "content_id": 7, "youtube_video_id": "vid00000007",
        "segments": [{"seq": 0, "en_text": "Hi."}],
    }]
    client = _FakeClient(items)

    class FakeAligner:
        def align(self, audio_path, segments):
            return {0: [{"w": "Hi", "s": 10, "e": 90}]}

    processed = transcript_agent.process_alignments_once(
        client, aligner=FakeAligner(), downloader=lambda vid: "/tmp/none.m4a"
    )
    assert processed == 1
    assert client.posts[0][0].endswith("/api/agent/transcripts/7/alignment")
    assert client.posts[0][1] == {"alignments": {0: [{"w": "Hi", "s": 10, "e": 90}]}}


def test_process_alignments_reports_failed_on_none(monkeypatch):
    from scripts import transcript_agent

    items = [{
        "content_id": 8, "youtube_video_id": "vid00000008",
        "segments": [{"seq": 0, "en_text": "Hi."}],
    }]
    client = _FakeClient(items)

    class FakeAligner:
        def align(self, audio_path, segments):
            return None  # 매핑 실패

    transcript_agent.process_alignments_once(
        client, aligner=FakeAligner(), downloader=lambda vid: "/tmp/none.m4a"
    )
    assert client.posts[0][0].endswith("/api/agent/transcripts/8/alignment/failed")
```

(참고: `downloader=lambda vid: "/tmp/none.m4a"` 는 실제 다운로드를 대체. FakeAligner 는 경로를 무시하므로 파일 없어도 됨. 정리 대상 디렉토리가 `/tmp` 가 되지 않도록 구현은 경로의 dirname 이 tempfile 계열일 때만 삭제 — 아래 구현 참고.)

- [ ] **Step 2: 실패 확인**

Run: `cd backend && uv run pytest tests/test_align_lib.py -v -k process_alignments`
Expected: FAIL — `process_alignments_once` 없음(AttributeError)

- [ ] **Step 3: 구현** — `backend/scripts/transcript_agent.py`

파일 최상단(기존 import 위)에 sys.path 션트 추가 — 스크립트 실행/테스트 양쪽에서 `scripts.lib` import 가능하게:

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/
```

파일 하단(`main()` 위)에 추가:

```python
_ALIGNER = None


def _default_aligner():
    global _ALIGNER
    if _ALIGNER is None:
        from scripts.lib.align import StableTsAligner

        _ALIGNER = StableTsAligner()
    return _ALIGNER


def process_alignments_once(client, aligner=None, downloader=None) -> int:
    """정렬 대기 콘텐츠를 오디오 정렬해 제출. 실패는 best-effort — 다음 주기 재시도."""
    import shutil
    import tempfile

    res = client.get(f"{SERVER}/api/agent/pending-alignments")
    res.raise_for_status()
    items = res.json()["items"]
    if not items:
        return 0
    log(f"정렬 대기 {len(items)}건")

    if downloader is None:
        from scripts.lib.align import download_audio

        downloader = download_audio

    done = 0
    for item in items:
        video_id = item["youtube_video_id"]
        segments = [(s["seq"], s["en_text"]) for s in item["segments"]]
        audio_dir = None
        try:
            audio_path = downloader(video_id)
            audio_dir = os.path.dirname(audio_path)
            engine = aligner or _default_aligner()
            alignments = engine.align(audio_path, segments)
        except FileNotFoundError:
            log("  [!] yt-dlp/ffmpeg 미설치 — 'brew install yt-dlp ffmpeg' 후 재시도")
            return done
        except Exception as exc:
            log(f"  [x] {video_id}: 오디오/정렬 실패 ({type(exc).__name__}) — 다음 주기 재시도")
            continue
        finally:
            if audio_dir and audio_dir.startswith(tempfile.gettempdir()):
                shutil.rmtree(audio_dir, ignore_errors=True)

        if not alignments:
            client.post(f"{SERVER}/api/agent/transcripts/{item['content_id']}/alignment/failed")
            log(f"  [-] {video_id}: 정렬 매핑 실패 — 대기열 제외 보고")
            continue
        submit = client.post(
            f"{SERVER}/api/agent/transcripts/{item['content_id']}/alignment",
            json={"alignments": alignments},
        )
        if submit.status_code == 202:
            log(f"  [o] {video_id}: 정렬 제출 ({submit.json().get('aligned')} 세그먼트)")
            done += 1
        else:
            log(f"  [x] {video_id}: 정렬 제출 실패 {submit.status_code}")
    return done
```

`main()` 루프에서 자막 처리 뒤에 정렬 패스 호출 추가:

```python
    while True:
        try:
            processed = process_once(client)
            if processed:
                log(f"{processed}건 처리 완료 — 서버가 번역/추출을 이어서 진행합니다")
            aligned = process_alignments_once(client)
            if aligned:
                log(f"{aligned}건 정렬 완료")
        except Exception as exc:
            log(f"[!] 오류: {type(exc).__name__}: {exc}")
        if once:
            break
        time.sleep(POLL_SECONDS)
```

- [ ] **Step 4: 통과 확인**

Run: `cd backend && uv run pytest tests/test_align_lib.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
cd backend && uv run ruff check . && uv run ruff format .
git add backend/scripts/transcript_agent.py backend/tests/test_align_lib.py
git commit -m "feat: 자막 수집기에 정렬 패스 통합 (pending-alignments 폴링)"
```

---

## Task 7: 프론트 — 단어 하이라이트 + 단어 탭 반복

**Files:**
- Modify: `frontend/src/lib/study-api.ts` (LibraryDetail 세그먼트 타입)
- Create: `frontend/src/components/media/TranscriptWords.tsx`
- Modify: `frontend/src/app/library/[id]/page.tsx`

**Interfaces:**
- Consumes: `GET /api/contents/{id}` 의 `segments[].words` (Task 4).
- Produces: `TranscriptWords` 컴포넌트, 라이브러리 상세의 단어 하이라이트/탭 반복.

- [ ] **Step 1: 타입 추가** — `frontend/src/lib/study-api.ts` 의 `LibraryDetail.segments` 항목에 `words` 추가

```typescript
export interface AlignedWord {
  w: string;
  s: number;
  e: number;
}

export interface LibraryDetail {
  id: number;
  title: string;
  source: string;
  youtube_video_id: string | null;
  segments: {
    seq: number;
    start_ms: number | null;
    end_ms: number | null;
    en_text: string;
    ko_text: string | null;
    words: AlignedWord[] | null;
  }[];
}
```

- [ ] **Step 2: 단어 렌더 컴포넌트 작성** — `frontend/src/components/media/TranscriptWords.tsx`

```tsx
"use client";

import type { AlignedWord } from "@/lib/study-api";

/** 문장을 단어 span 으로 렌더 — 현재 재생 단어 하이라이트 + 탭하면 그 단어 반복.
 *  words 가 없으면(미정렬) 평문으로 폴백. (docs/specs/word-alignment.md) */
export function TranscriptWords({
  words,
  text,
  nowMs,
  onWordTap,
}: {
  words: AlignedWord[] | null;
  text: string;
  nowMs: number;
  onWordTap: (word: AlignedWord) => void;
}) {
  if (!words || words.length === 0) {
    return <span>{text}</span>;
  }
  return (
    <span>
      {words.map((word, i) => {
        const active = nowMs >= word.s && nowMs < word.e;
        return (
          <span key={i}>
            <button
              type="button"
              onClick={() => onWordTap(word)}
              className={`rounded px-0.5 transition ${
                active ? "bg-brick-yellow/70 font-bold" : "hover:bg-ink/10"
              }`}
            >
              {word.w}
            </button>{" "}
          </span>
        );
      })}
    </span>
  );
}
```

- [ ] **Step 3: 라이브러리 상세 통합** — `frontend/src/app/library/[id]/page.tsx`

(a) import 추가:

```tsx
import { TranscriptWords } from "@/components/media/TranscriptWords";
import { studyApi, type LibraryDetail, type AlignedWord } from "@/lib/study-api";
```

(b) `nowMs` 상태 추가 (`currentSeq` 근처):

```tsx
  const [nowMs, setNowMs] = useState(0);
```

(c) 동기 폴링 안에서 `now` 계산 직후 상태 반영 (기존 `const now = player.getCurrentTime() * 1000;` 다음 줄):

```tsx
        setNowMs(now);
```

(d) 단어 반복 함수 추가 (`playSegment` 근처):

```tsx
  function playWord(word: AlignedWord) {
    const player = playerRef.current;
    if (!player) return;
    const start = word.s / 1000;
    // 단어가 짧아 최소 400ms 보장 — 즉시 정지·재시킹 반복 방지
    const end = Math.max(word.e, word.s + 400) / 1000;
    rangeRef.current = { start, end };
    setLoop(true);
    loopRef.current = true;
    player.seekTo(start, true);
    player.playVideo();
  }
```

(e) 현재 문장 표시부(`<p className="text-lg font-medium">{current.en_text}</p>`)를 교체:

```tsx
                  <p className="text-lg font-medium">
                    <TranscriptWords
                      words={current.words}
                      text={current.en_text}
                      nowMs={nowMs}
                      onWordTap={playWord}
                    />
                  </p>
```

- [ ] **Step 4: 린트 + 빌드(타입체크)**

Run: `cd frontend && npm run lint && npm run build`
Expected: 린트 0 에러, 빌드 성공(타입 에러 0)

- [ ] **Step 5: 헤드리스 시각 검증**

dev 서버(`PORT=3399 npm run dev`)를 띄우고 라이브러리 상세를 Playwright route 목킹으로 캡처(프로젝트 관례: `/api/contents/{id}` fulfill 로 `words` 포함 세그먼트 주입). 확인 항목:
- 현재 단어가 노란 배경으로 강조되는가
- 단어 탭 시 해당 단어 구간이 반복되는가 (loop 체크 자동 on)
- `words: null` 세그먼트는 평문으로 정상 렌더(폴백)

데스크톱(1440) + 모바일(375) 2뷰포트. (frontend-verify 규칙)

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/lib/study-api.ts frontend/src/components/media/TranscriptWords.tsx frontend/src/app/library/[id]/page.tsx
git commit -m "feat: 라이브러리 단어 하이라이트 + 단어 탭 반복"
```

---

## Task 8: 스펙 참조 갱신 + 최종 검증

**Files:**
- Modify: `docs/specs/content-pipeline.md` (단어 정렬 참조 한 줄)

- [ ] **Step 1: content-pipeline.md 단계 2 말미에 참조 추가**

```markdown
단어 정렬 (2026-07-22): 문장 경계는 위 보간이 기본값이고, 로컬 에이전트가 오디오를 받아 단어별 시각을 채우면(`transcript_segments.words`) 경계가 단어 시각에서 정확히 파생된다. 상세: [word-alignment.md](word-alignment.md).
```

- [ ] **Step 2: 백엔드 전체 검증**

Run: `cd backend && uv run ruff check . && uv run ruff format . && uv run pytest -q`
Expected: 전부 통과, 신규 테스트 포함 (기존 대비 +약 15개)

- [ ] **Step 3: 프론트 최종 검증**

Run: `cd frontend && npm run lint && npm run build`
Expected: 통과

- [ ] **Step 4: 커밋**

```bash
git add docs/specs/content-pipeline.md
git commit -m "docs: content-pipeline 에 단어 정렬 참조 추가"
```

---

## 배포 후 수동 셋업 (에이전트 머신)

구현·머지 후 로컬 Mac 에이전트에서 1회:

```bash
brew install ffmpeg          # yt-dlp 는 이미 backend 의존성
cd backend && uv sync --group align    # stable-ts + torch (첫 설치 시 시간 소요)
launchctl kickstart -k gui/$(id -u)/com.esl.transcript-agent   # 에이전트 재시작
```

첫 정렬 시 stable-ts 가 `base.en` 모델(~140MB)을 자동 내려받는다. 로그(`~/Library/Logs/esl-transcript-agent.log`)에서 "정렬 완료" 확인. 기존 콘텐츠가 배치(20건)로 시간에 걸쳐 백필된다.

---

## 평가 기준 (완료 시 자가 점검)

| 기준 | 목표 |
|---|---|
| 완성도 | 스펙 8개 영역(모델·마이그레이션·서비스·엔드포인트·API노출·에이전트lib·에이전트루프·프론트) 전부 구현 |
| 견고성 | best-effort 폴백, 멱등, 정렬 실패 격리, words null 폴백 — 테스트로 검증 |
| 일관성 | 기존 agent.py/pipeline 패턴 재사용, ruff 통과, 도메인 파일명 규약 |
| 간결성 | 순수 로직 분리(remap/apply_alignment), 파일별 단일 책임 |
