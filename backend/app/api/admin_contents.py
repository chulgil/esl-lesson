"""백오피스 콘텐츠/항목 API (docs/specs/backoffice.md). 전 라우트 admin 가드."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_admin
from app.models import Content, ExtractionJob, ItemOccurrence, LearningItem, TranscriptSegment
from app.models.user import User
from app.services.youtube import parse_video_id
from app.workers.queue import enqueue

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class ContentCreate(BaseModel):
    source: Literal["youtube", "manual"]
    url: str | None = None
    title: str | None = Field(default=None, max_length=500)
    script_en: str | None = None
    script_ko: str | None = None

    @model_validator(mode="after")
    def check_by_source(self) -> "ContentCreate":
        if self.source == "youtube" and not self.url:
            raise ValueError("youtube source requires url")
        if self.source == "manual" and (not self.title or not self.script_en):
            raise ValueError("manual source requires title and script_en")
        return self


@router.post("/contents", status_code=status.HTTP_202_ACCEPTED)
async def create_content(
    body: ContentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    if body.source == "youtube":
        video_id = parse_video_id(body.url or "")
        if video_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid youtube url")
        dup = await db.execute(select(Content.id).where(Content.youtube_video_id == video_id))
        existing_id = dup.scalar_one_or_none()
        if existing_id is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"already registered: content {existing_id}"
            )
        content = Content(
            source="youtube",
            youtube_video_id=video_id,
            url=body.url,
            title=body.title or f"(제목 조회 중) {video_id}",
            created_by=admin.id,
        )
        db.add(content)
        await db.commit()
    else:
        content = Content(source="manual", url=body.url, title=body.title, created_by=admin.id)
        db.add(content)
        await db.flush()
        for seq, line in enumerate(_split_sentences(body.script_en or "")):
            db.add(TranscriptSegment(content_id=content.id, seq=seq, en_text=line))
        ko_lines = _split_sentences(body.script_ko or "") if body.script_ko else []
        if ko_lines:
            segments = await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.content_id == content.id)
                .order_by(TranscriptSegment.seq)
            )
            seg_list = list(segments.scalars())
            if len(ko_lines) == len(seg_list):
                for seg, ko in zip(seg_list, ko_lines, strict=True):
                    seg.ko_text = ko
        await db.commit()

    enqueue(content.id)
    return {"id": content.id, "status": content.status}


def _split_sentences(text: str) -> list[str]:
    """수기 스크립트 문장 분리: 줄바꿈 우선, 없으면 문장부호."""
    import re

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]


@router.get("/contents")
async def list_contents(
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    query = select(Content).order_by(Content.id.desc())
    if status_filter:
        query = query.where(Content.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.offset((page - 1) * size).limit(size))).scalars().all()
    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": c.id,
                "source": c.source,
                "title": c.title,
                "status": c.status,
                "youtube_video_id": c.youtube_video_id,
                "error_message": c.error_message,
                "created_at": c.created_at,
            }
            for c in rows
        ],
    }


@router.get("/contents/{content_id}")
async def get_content(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    content = await db.get(Content, content_id)
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")

    segments = (
        (
            await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.content_id == content_id)
                .order_by(TranscriptSegment.seq)
            )
        )
        .scalars()
        .all()
    )
    jobs = (
        (await db.execute(select(ExtractionJob).where(ExtractionJob.content_id == content_id)))
        .scalars()
        .all()
    )
    items = (
        await db.execute(
            select(LearningItem, ItemOccurrence)
            .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
            .where(ItemOccurrence.content_id == content_id)
            .order_by(LearningItem.item_type, LearningItem.id)
        )
    ).all()
    return {
        "id": content.id,
        "source": content.source,
        "url": content.url,
        "title": content.title,
        "title_ko": content.title_ko,
        "status": content.status,
        "error_message": content.error_message,
        "segments": [
            {
                "id": s.id,
                "seq": s.seq,
                "start_ms": s.start_ms,
                "en_text": s.en_text,
                "ko_text": s.ko_text,
            }
            for s in segments
        ],
        "jobs": [
            {
                "step": j.step,
                "status": j.status,
                "attempt": j.attempt,
                "error": j.error,
                "payload": j.payload,
            }
            for j in jobs
        ],
        "items": [
            {
                "id": item.id,
                "item_type": item.item_type,
                "level": item.level,
                "en_text": item.en_text,
                "ko_text": item.ko_text,
                "hint_thinking": item.hint_thinking,
                "pattern_template": item.pattern_template,
                "difficulty_hint": item.difficulty_hint,
                "review_status": item.review_status,
                "context_en": occ.context_en,
            }
            for item, occ in items
        ],
    }


@router.post("/contents/{content_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_content(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    content = await db.get(Content, content_id)
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    if content.status not in ("failed", "ready"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot retry in {content.status}")
    content.status = "pending"
    content.error_message = None
    await db.commit()
    enqueue(content_id)
    return {"id": content_id, "status": "pending"}


@router.delete("/contents/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    content = await db.get(Content, content_id)
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    await db.delete(content)
    # 다른 출처가 없는 고아 항목 정리
    orphans = await db.execute(
        select(LearningItem).where(
            ~select(ItemOccurrence.id).where(ItemOccurrence.item_id == LearningItem.id).exists()
        )
    )
    for item in orphans.scalars():
        await db.delete(item)
    await db.commit()


class SegmentPatch(BaseModel):
    en_text: str | None = None
    ko_text: str | None = None


@router.patch("/segments/{segment_id}")
async def patch_segment(
    segment_id: int, body: SegmentPatch, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    segment = await db.get(TranscriptSegment, segment_id)
    if segment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "segment not found")
    if body.en_text is not None:
        segment.en_text = body.en_text
    if body.ko_text is not None:
        segment.ko_text = body.ko_text
    await db.commit()
    return {"id": segment.id, "en_text": segment.en_text, "ko_text": segment.ko_text}


class ItemPatch(BaseModel):
    en_text: str | None = None
    ko_text: str | None = None
    hint_thinking: str | None = None
    review_status: Literal["pending", "approved", "rejected"] | None = None


@router.patch("/items/{item_id}")
async def patch_item(
    item_id: int, body: ItemPatch, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    item = await db.get(LearningItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item not found")
    if body.review_status == "approved" and item.item_type == "sentence":
        hint = body.hint_thinking if body.hint_thinking is not None else item.hint_thinking
        if not hint:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "sentence item requires hint_thinking before approval",
            )
    for field in ("en_text", "ko_text", "hint_thinking", "review_status"):
        value = getattr(body, field)
        if value is not None:
            setattr(item, field, value)
    await db.commit()
    return {"id": item.id, "review_status": item.review_status}


@router.post("/contents/{content_id}/approve-all")
async def approve_all(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    items = (
        (
            await db.execute(
                select(LearningItem)
                .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
                .where(
                    ItemOccurrence.content_id == content_id,
                    LearningItem.review_status == "pending",
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    approved = 0
    skipped = 0
    for item in items:
        # 사고 힌트 없는 문장은 일괄 승인에서 제외 (개별 검수 필요)
        if item.item_type == "sentence" and not item.hint_thinking:
            skipped += 1
            continue
        item.review_status = "approved"
        approved += 1
    await db.commit()
    return {"approved": approved, "skipped": skipped}


@router.get("/items")
async def search_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    item_type: Annotated[str | None, Query(alias="type")] = None,
    review_status: Annotated[str | None, Query(alias="status")] = None,
    q: str | None = None,
    page: int = 1,
    size: int = 50,
) -> dict:
    query = select(LearningItem).order_by(LearningItem.id.desc())
    if item_type:
        query = query.where(LearningItem.item_type == item_type)
    if review_status:
        query = query.where(LearningItem.review_status == review_status)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            func.lower(LearningItem.en_text).like(pattern)
            | func.lower(LearningItem.ko_text).like(pattern)
        )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.offset((page - 1) * size).limit(size))).scalars().all()
    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": i.id,
                "item_type": i.item_type,
                "en_text": i.en_text,
                "ko_text": i.ko_text,
                "review_status": i.review_status,
                "difficulty_hint": i.difficulty_hint,
            }
            for i in rows
        ],
    }


@router.get("/dashboard")
async def dashboard(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    pending_items = (
        await db.execute(select(func.count()).where(LearningItem.review_status == "pending"))
    ).scalar_one()
    failed_contents = (
        await db.execute(select(func.count()).where(Content.status == "failed"))
    ).scalar_one()
    extracting = (
        await db.execute(select(func.count()).where(Content.status.in_(("pending", "extracting"))))
    ).scalar_one()
    total_contents = (await db.execute(select(func.count(Content.id)))).scalar_one()
    return {
        "pending_items": pending_items,
        "failed_contents": failed_contents,
        "in_progress_contents": extracting,
        "total_contents": total_contents,
    }
