"""백오피스 콘텐츠/항목 API — 공용(public) 콘텐츠 전용 (docs/specs/backoffice.md)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_admin
from app.models import Content, ItemOccurrence, LearningItem, TranscriptSegment
from app.models.user import User
from app.services.content_service import (
    ContentCreate,
    content_detail,
    content_summary,
    create_content,
    delete_content_row,
    retry_content_row,
)
from app.workers.queue import enqueue

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


async def get_public_content(db: AsyncSession, content_id: int) -> Content:
    content = await db.get(Content, content_id)
    if content is None or content.visibility != "public":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    return content


@router.post("/contents", status_code=status.HTTP_202_ACCEPTED)
async def create_public_content(
    body: ContentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> dict:
    content = await create_content(db, body, admin.id, visibility="public")
    enqueue(content.id)
    return {"id": content.id, "status": content.status}


@router.get("/contents")
async def list_contents(
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    query = select(Content).where(Content.visibility == "public").order_by(Content.id.desc())
    if status_filter:
        query = query.where(Content.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = ((await db.execute(query.offset((page - 1) * size).limit(size))).scalars()).all()
    return {"total": total, "page": page, "items": [content_summary(c) for c in rows]}


@router.get("/contents/{content_id}")
async def get_content(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    content = await get_public_content(db, content_id)
    return await content_detail(db, content)


@router.post("/contents/{content_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_content(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    content = await get_public_content(db, content_id)
    retry_content_row(content)
    await db.commit()
    enqueue(content_id)
    return {"id": content_id, "status": "pending"}


@router.delete("/contents/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(content_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    content = await get_public_content(db, content_id)
    await delete_content_row(db, content)


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
    rows = ((await db.execute(query.offset((page - 1) * size).limit(size))).scalars()).all()
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
        await db.execute(
            select(func.count()).where(Content.status == "failed", Content.visibility == "public")
        )
    ).scalar_one()
    extracting = (
        await db.execute(
            select(func.count()).where(
                Content.status.in_(("pending", "extracting")), Content.visibility == "public"
            )
        )
    ).scalar_one()
    total_contents = (
        await db.execute(select(func.count(Content.id)).where(Content.visibility == "public"))
    ).scalar_one()
    return {
        "pending_items": pending_items,
        "failed_contents": failed_contents,
        "in_progress_contents": extracting,
        "total_contents": total_contents,
    }
