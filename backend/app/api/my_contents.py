"""개인 콘텐츠 API — 서비스(/my)에서 본인 전용 등록/관리 (docs/specs/content-pipeline.md 가시성)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.study import kst_day_start
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Content, ItemOccurrence, LearningItem, ReviewCard, User
from app.models.user import ROLE_ADMIN
from app.services.content_service import (
    ContentCreate,
    content_detail,
    content_summary,
    create_content,
    delete_content_row,
    retry_content_row,
)
from app.workers.queue import enqueue

router = APIRouter(prefix="/my", tags=["my"])

DAILY_PRIVATE_LIMIT = 10  # 개인 등록 일일 한도 (2026-07-11 사용자 결정, 관리자 무제한)


async def get_my_content(db: AsyncSession, content_id: int, user: User) -> Content:
    content = await db.get(Content, content_id)
    if content is None or content.visibility != "private" or content.created_by != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    return content


@router.post("/contents", status_code=status.HTTP_202_ACCEPTED)
async def create_my_content(
    body: ContentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if user.role != ROLE_ADMIN:
        day_start = kst_day_start(datetime.now(UTC))
        today_count = (
            await db.execute(
                select(func.count(Content.id)).where(
                    Content.created_by == user.id,
                    Content.visibility == "private",
                    Content.created_at >= day_start,
                )
            )
        ).scalar_one()
        if today_count >= DAILY_PRIVATE_LIMIT:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"daily limit reached ({DAILY_PRIVATE_LIMIT}/day)",
            )
    content = await create_content(db, body, user.id, visibility="private")
    enqueue(content.id)
    return {"id": content.id, "status": content.status}


@router.get("/contents")
async def list_my_contents(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: int = 1,
    size: int = 20,
) -> dict:
    query = (
        select(Content)
        .where(Content.visibility == "private", Content.created_by == user.id)
        .order_by(Content.id.desc())
    )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = ((await db.execute(query.offset((page - 1) * size).limit(size))).scalars()).all()
    return {"total": total, "page": page, "items": [content_summary(c) for c in rows]}


@router.get("/contents/{content_id}")
async def get_my_content_detail(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    content = await get_my_content(db, content_id, user)
    detail = await content_detail(db, content)
    # 내 카드의 suspend 상태를 항목에 병합 (개인 항목 제외 = 카드 suspend)
    cards = dict(
        (
            await db.execute(
                select(ReviewCard.item_id, ReviewCard.suspended).where(
                    ReviewCard.user_id == user.id,
                    ReviewCard.item_id.in_([i["id"] for i in detail["items"]] or [0]),
                )
            )
        ).all()
    )
    for item in detail["items"]:
        item["excluded"] = bool(cards.get(item["id"], False))
    return detail


@router.post("/contents/{content_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_my_content(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    content = await get_my_content(db, content_id, user)
    retry_content_row(content)
    await db.commit()
    enqueue(content_id)
    return {"id": content_id, "status": "pending"}


@router.delete("/contents/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_content(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    content = await get_my_content(db, content_id, user)
    await delete_content_row(db, content)


@router.post("/items/{item_id}/exclude")
async def exclude_item(
    item_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """개인 항목 학습 제외 — 전역 상태 대신 내 카드 suspend (공유 항목 안전)."""
    return await _set_item_excluded(db, item_id, user, True)


@router.post("/items/{item_id}/include")
async def include_item(
    item_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return await _set_item_excluded(db, item_id, user, False)


async def _set_item_excluded(db: AsyncSession, item_id: int, user: User, excluded: bool) -> dict:
    item = await db.get(LearningItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item not found")
    # 내 콘텐츠 출처가 있는 항목만 제외/복귀 가능
    has_mine = (
        await db.execute(
            select(ItemOccurrence.id)
            .join(Content, Content.id == ItemOccurrence.content_id)
            .where(
                ItemOccurrence.item_id == item_id,
                Content.created_by == user.id,
                Content.visibility == "private",
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if has_mine is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your item")

    card = (
        await db.execute(
            select(ReviewCard).where(ReviewCard.user_id == user.id, ReviewCard.item_id == item_id)
        )
    ).scalar_one_or_none()
    if card is None:
        card = ReviewCard(user_id=user.id, item_id=item_id, state="new", due_at=datetime.now(UTC))
        db.add(card)
    card.suspended = excluded
    await db.commit()
    return {"item_id": item_id, "excluded": excluded}
