"""내 콘텐츠 API — 담기(구독) 구조 (docs/specs/content-governance.md).

콘텐츠 등록은 관리자 전용이다. 사용자는 라이브러리의 공용 콘텐츠를 담아서
학습하고, 담은 것만 학습 큐·게임에 편입된다.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.content_service import (
    content_detail,
    content_summary,
    delete_content_row,
    retry_content_row,
)
from app.services.visibility import subscribed_content_ids
from app.workers.queue import enqueue

router = APIRouter(prefix="/my", tags=["my"])


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


async def _already_subscribed(db: AsyncSession, content_id: int, user_id: int) -> bool:
    exists = (
        await db.execute(
            select(ContentSubscription.id).where(
                ContentSubscription.content_id == content_id,
                ContentSubscription.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    return exists is not None


async def subscribe(db: AsyncSession, content_id: int, user_id: int) -> None:
    if await _already_subscribed(db, content_id, user_id):
        return
    db.add(ContentSubscription(content_id=content_id, user_id=user_id))
    try:
        await db.commit()
    except IntegrityError:
        # 동시 더블탭 경합 (uq_subscriptions_content_user) — 이미 구독됨,
        # 멱등 처리 (기존 202 계약 유지, 2026-08-11 500 픽스)
        await db.rollback()


@router.post("/contents/{content_id}/subscribe", status_code=status.HTTP_202_ACCEPTED)
async def subscribe_content(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """담기 — 라이브러리의 공용 콘텐츠를 내 학습에 편입 (멱등).

    예외: **내 chat 덱(내가 쓰는 말)** 은 private 여도 재담기 허용 —
    문서함 빼기 후 되돌리는 경로 (docs/specs/my-phrases.md 담기/빼기)."""
    content = await db.get(Content, content_id)
    my_chat_deck = (
        content is not None and content.source == "chat" and content.created_by == user.id
    )
    # 준비 안 된/개인 콘텐츠는 담을 수 없다. 존재 여부도 흘리지 않도록 동일 404
    if (
        content is None
        or content.status != "ready"
        or (content.visibility != "public" and not my_chat_deck)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content not found")
    # subscribe() 내부 rollback(동시 경합 시)이 content 를 만료시킬 수 있어
    # content_id 파라미터(이미 아는 값)를 그대로 쓴다 — 재접근 없이 안전
    await subscribe(db, content_id, user.id)
    return {"id": content_id, "subscribed": True}


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
    # 공용 콘텐츠 재추출은 관리자만 — 담기가 열리면서 사용자가 관리자 콘텐츠의
    # AI 재추출 비용을 트리거할 수 있게 되는 구멍을 막는다 (content-governance.md)
    if content.visibility != "private":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
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
    """구독 해지. 마지막 구독자가 떠난 개인 콘텐츠는 본체 삭제 (공용은 유지).

    예외: **chat 덱(내가 쓰는 말)** 은 본체를 지우지 않는다 — 빼기는 학습
    일시정지이지 수집분 폐기가 아니다. 수집·편집은 계속되고 재담기 시
    카드 진행 그대로 복귀 (docs/specs/my-phrases.md 담기/빼기)."""
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
    if content.visibility == "private" and remaining == 0 and content.source != "chat":
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
