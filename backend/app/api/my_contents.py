"""개인 콘텐츠 API — 구독 구조 (docs/specs/content-pipeline.md 콘텐츠 가시성).

같은 유튜브 영상은 콘텐츠 1행을 공유하고, 사용자별로 content_subscriptions 로 연결한다.
이미 추출된 영상을 등록하면 재추출 없이 즉시 구독된다 (AI 비용 0).
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.study import kst_day_start
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import (
    Content,
    ContentSubscription,
    ItemOccurrence,
    LearningItem,
    ReviewCard,
    User,
)
from app.models.user import ROLE_ADMIN
from app.services.content_service import (
    ContentCreate,
    content_detail,
    content_summary,
    create_content,
    delete_content_row,
    retry_content_row,
)
from app.services.visibility import subscribed_content_ids
from app.services.youtube import parse_video_id
from app.workers.queue import enqueue

router = APIRouter(prefix="/my", tags=["my"])

DAILY_PRIVATE_LIMIT = 10  # 신규 생성(=AI 추출 비용)만 카운트. 기존 콘텐츠 구독은 무제한.


async def get_subscribed_content(db: AsyncSession, content_id: int, user: User) -> Content:
    content = await db.get(Content, content_id)
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    subscribed = (
        await db.execute(
            select(ContentSubscription.id).where(
                ContentSubscription.content_id == content_id,
                ContentSubscription.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if subscribed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    return content


async def subscribe(db: AsyncSession, content_id: int, user_id: int) -> None:
    exists = (
        await db.execute(
            select(ContentSubscription.id).where(
                ContentSubscription.content_id == content_id,
                ContentSubscription.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        db.add(ContentSubscription(content_id=content_id, user_id=user_id))
        await db.commit()


async def _check_daily_limit(db: AsyncSession, user: User) -> None:
    if user.role == ROLE_ADMIN:
        return
    day_start = kst_day_start(datetime.now(UTC))
    today_created = (
        await db.execute(
            select(func.count(Content.id)).where(
                Content.created_by == user.id,
                Content.visibility == "private",
                Content.created_at >= day_start,
            )
        )
    ).scalar_one()
    if today_created >= DAILY_PRIVATE_LIMIT:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"daily limit reached ({DAILY_PRIVATE_LIMIT}/day)",
        )


@router.post("/contents", status_code=status.HTTP_202_ACCEPTED)
async def create_my_content(
    body: ContentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    # 동일 영상은 기존 콘텐츠에 구독으로 연결 — 재추출 없이 즉시 사용 (한도 미차감)
    if body.source == "youtube":
        video_id = parse_video_id(body.url or "")
        if video_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid youtube url")
        existing = (
            await db.execute(select(Content).where(Content.youtube_video_id == video_id))
        ).scalar_one_or_none()
        if existing is not None:
            await subscribe(db, existing.id, user.id)
            return {"id": existing.id, "status": existing.status, "reused": True}

    await _check_daily_limit(db, user)
    content = await create_content(db, body, user.id, visibility="private")
    await subscribe(db, content.id, user.id)
    enqueue(content.id)
    return {"id": content.id, "status": content.status, "reused": False}


@router.get("/contents")
async def list_my_contents(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: int = 1,
    size: int = 20,
) -> dict:
    query = (
        select(Content)
        .where(Content.id.in_(subscribed_content_ids(user.id)))
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
    content = await get_subscribed_content(db, content_id, user)
    detail = await content_detail(db, content)
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
    content = await get_subscribed_content(db, content_id, user)
    retry_content_row(content)
    await db.commit()
    enqueue(content_id)
    return {"id": content_id, "status": "pending"}


@router.delete("/contents/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe_my_content(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """구독 해지. 마지막 구독자가 떠난 개인 콘텐츠는 본체 삭제 (공용은 유지)."""
    content = await get_subscribed_content(db, content_id, user)
    await db.execute(
        ContentSubscription.__table__.delete().where(
            ContentSubscription.content_id == content_id,
            ContentSubscription.user_id == user.id,
        )
    )
    await db.commit()
    remaining = (
        await db.execute(
            select(func.count(ContentSubscription.id)).where(
                ContentSubscription.content_id == content_id
            )
        )
    ).scalar_one()
    if content.visibility == "private" and remaining == 0:
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
    # 내가 구독한 콘텐츠 출처가 있는 항목만 제외/복귀 가능
    has_mine = (
        await db.execute(
            select(ItemOccurrence.id)
            .where(
                ItemOccurrence.item_id == item_id,
                ItemOccurrence.content_id.in_(subscribed_content_ids(user.id)),
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
