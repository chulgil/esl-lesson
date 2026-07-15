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
from app.services.pipeline import _align_ko_by_time
from app.services.youtube import Snippet, merge_into_sentences
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
                en_text=snippet.text,
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
