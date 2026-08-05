"""로컬 자막 수집기 API (docs/specs/content-pipeline.md 차단 대응).

서버(클라우드 IP)가 유튜브에 차단되므로, 집 IP를 가진 로컬 수집기가
대기 목록을 폴링해 자막을 대신 가져다 제출한다. 토큰(X-Agent-Token) 인증.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.models import Content, ExtractionJob, TranscriptSegment
from app.services.alignment import apply_alignment
from app.services.pipeline import _align_ko_by_time
from app.services.youtube import Snippet, merge_into_sentences, strip_caption_credits
from app.workers.queue import enqueue

router = APIRouter(prefix="/agent", tags=["agent"])


async def require_agent_token(
    x_agent_token: Annotated[str | None, Header()] = None,
) -> None:
    token = get_settings().agent_token
    if not token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent api disabled")
    if not x_agent_token or x_agent_token != token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid agent token")


@router.get("/pending-transcripts", dependencies=[Depends(require_agent_token)])
async def pending_transcripts(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """자막 대기 중인 유튜브 콘텐츠 목록 (세그먼트 없음 + transcript 단계 실패)."""
    has_segments = exists(
        select(TranscriptSegment.id).where(TranscriptSegment.content_id == Content.id)
    )
    transcript_failed = exists(
        select(ExtractionJob.id).where(
            ExtractionJob.content_id == Content.id,
            ExtractionJob.step == "transcript",
            ExtractionJob.status == "failed",
        )
    )
    rows = (
        (
            await db.execute(
                select(Content)
                .where(
                    # pending 전용 — failed 는 자막 없음이 확정된 콘텐츠(수집기 보고
                    # 또는 서버 직접 확인)라 재수집 대상이 아니다. 재시도 시 파이프
                    # 라인이 다시 pending 으로 되돌리므로 그때 재노출된다.
                    Content.source == "youtube",
                    Content.status == "pending",
                    ~has_segments,
                    transcript_failed,
                )
                .order_by(Content.id)
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    return {"items": [{"content_id": c.id, "youtube_video_id": c.youtube_video_id} for c in rows]}


NO_TRANSCRIPT_MESSAGE = "영어 자막이 없는 영상이에요 — 자막이 있는 영상으로 다시 등록해 주세요"


@router.post("/transcripts/{content_id}/missing", dependencies=[Depends(require_agent_token)])
async def report_transcript_missing(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """수집기가 확인한 '영어 자막 없음' 확정 보고 → 실패 종결, 대기 목록에서 제거.

    보고 없이는 자막 없는 영상이 '자막 준비 중'으로 영원히 남고 수집기가
    같은 영상을 30초마다 재조회한다. 재시도 엔드포인트로 재수집 가능.
    """
    content = await db.get(Content, content_id)
    if content is None or content.source != "youtube":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    existing = (
        await db.execute(
            select(TranscriptSegment.id).where(TranscriptSegment.content_id == content_id).limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        # 다른 경로로 이미 자막이 들어옴 — 뒤늦은 보고로 덮어쓰지 않는다
        return {"content_id": content_id, "status": content.status, "skipped": True}

    job = (
        await db.execute(
            select(ExtractionJob).where(
                ExtractionJob.content_id == content_id, ExtractionJob.step == "transcript"
            )
        )
    ).scalar_one_or_none()
    if job is None:
        job = ExtractionJob(content_id=content_id, step="transcript")
        db.add(job)
    job.status = "failed"
    job.error = NO_TRANSCRIPT_MESSAGE
    job.payload = {"source": "local_agent", "reason": "no_transcript"}

    content.status = "failed"
    content.error_message = NO_TRANSCRIPT_MESSAGE
    await db.commit()
    return {"content_id": content_id, "status": "failed"}


class SnippetBody(BaseModel):
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class TranscriptSubmit(BaseModel):
    is_generated: bool = False
    en_snippets: list[SnippetBody] = Field(min_length=1)
    ko_snippets: list[SnippetBody] = Field(default_factory=list)


@router.post(
    "/transcripts/{content_id}",
    dependencies=[Depends(require_agent_token)],
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_transcript(
    content_id: int,
    body: TranscriptSubmit,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """수집기가 가져온 자막 제출 → 문장 병합/정렬 후 저장, 파이프라인 재개."""
    content = await db.get(Content, content_id)
    if content is None or content.source != "youtube":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    existing = (
        await db.execute(
            select(TranscriptSegment.id).where(TranscriptSegment.content_id == content_id).limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {"content_id": content_id, "status": content.status, "skipped": True}

    en = [Snippet(text=s.text, start_ms=s.start_ms, end_ms=s.end_ms) for s in body.en_snippets]
    sentences = merge_into_sentences(en)
    ko = [Snippet(text=s.text, start_ms=s.start_ms, end_ms=s.end_ms) for s in body.ko_snippets]
    ko_texts = _align_ko_by_time(sentences, ko) if ko else {}

    for seq, snippet in enumerate(sentences):
        db.add(
            TranscriptSegment(
                content_id=content_id,
                seq=seq,
                start_ms=snippet.start_ms,
                end_ms=snippet.end_ms,
                # 선두 자막 크레딧(Translator:/Reviewer:) 제거 (2026-08-05 검증)
                en_text=strip_caption_credits(snippet.text),
                ko_text=ko_texts.get(seq),
            )
        )

    job = (
        await db.execute(
            select(ExtractionJob).where(
                ExtractionJob.content_id == content_id, ExtractionJob.step == "transcript"
            )
        )
    ).scalar_one_or_none()
    if job is None:
        job = ExtractionJob(content_id=content_id, step="transcript")
        db.add(job)
    job.status = "done"
    job.error = None
    job.payload = {"segments": len(sentences), "source": "local_agent", "ko_matched": len(ko_texts)}

    content.status = "pending"
    content.error_message = None
    await db.commit()

    enqueue(content_id)  # 번역/추출은 서버가 이어서 진행
    return {"content_id": content_id, "segments": len(sentences), "status": "pending"}


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
    alignments = {seq: [w.model_dump() for w in words] for seq, words in body.alignments.items()}
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
    if job.status == "done":
        return {"content_id": content_id, "skipped": True}
    job.status = "failed"
    job.error = "audio unavailable for alignment"
    job.payload = {"source": "local_agent", "reason": "audio_unavailable"}
    await db.commit()
    return {"content_id": content_id, "status": "failed"}
