"""알림 센터 API — 목록·읽음 (docs/specs/notifications.md)."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Notification, User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict:
    # 읽은 알림은 24시간 뒤 목록에서 제외 — 안읽음은 기간 무관 유지.
    # 읽었는데도 목록에 영구 잔류해 "안 사라진다"로 체감 (2026-07-31 보고)
    read_keep_after = datetime.now(UTC) - timedelta(hours=24)
    rows = (
        (
            await db.execute(
                select(Notification)
                .where(
                    Notification.user_id == user.id,
                    or_(
                        Notification.read_at.is_(None),
                        Notification.read_at > read_keep_after,
                    ),
                )
                .order_by(Notification.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    # 배지는 목록(limit)과 무관하게 안읽음 총수 — 잘린 페이지로 배지가 줄면 안 됨
    unread = (
        await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id, Notification.read_at.is_(None)
            )
        )
    ).scalar_one()
    return {
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "payload": n.payload,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat(),
            }
            for n in rows
        ],
        "unread": unread,
    }


class ReadBody(BaseModel):
    all: bool = False
    ids: list[int] = Field(default_factory=list)


@router.post("/read")
async def mark_read(
    body: ReadBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """읽음 처리 — user_id 필터로 내 알림만. 타인 id 가 섞여 있어도 조용히 무시.

    ORM 속성 갱신 사용 (bulk UPDATE 금지) — 같은 세션의 identity map 이
    stale read_at 을 돌려주는 문제를 피한다 (사용자당 행 수 소규모 전제)."""
    query = select(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    )
    if not body.all:
        query = query.where(Notification.id.in_(body.ids))
    rows = (await db.execute(query)).scalars().all()
    now = datetime.now(UTC)
    for row in rows:
        row.read_at = now
    await db.commit()
    return {"ok": True}
