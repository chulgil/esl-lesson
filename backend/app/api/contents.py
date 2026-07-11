"""학습자용 콘텐츠 라이브러리 (읽기 전용, ready 콘텐츠만).

노출: 공용(public) 전체 + 내 개인(private) 콘텐츠 (docs/specs/content-pipeline.md).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Content, ItemOccurrence, TranscriptSegment, User
from app.services.visibility import subscribed_content_ids

router = APIRouter(prefix="/contents", tags=["contents"])


def visible_content_clause(user_id: int):
    return or_(
        Content.visibility == "public",
        and_(
            Content.visibility == "private",
            Content.id.in_(subscribed_content_ids(user_id)),
        ),
    )


@router.get("")
async def list_ready_contents(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: int = 1,
    size: int = 20,
) -> dict:
    base = (
        select(Content)
        .where(Content.status == "ready", visible_content_clause(user.id))
        .order_by(Content.id.desc())
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = ((await db.execute(base.offset((page - 1) * size).limit(size))).scalars()).all()
    item_counts = (
        dict(
            (
                await db.execute(
                    select(
                        ItemOccurrence.content_id,
                        func.count(func.distinct(ItemOccurrence.item_id)),
                    )
                    .where(ItemOccurrence.content_id.in_([c.id for c in rows]))
                    .group_by(ItemOccurrence.content_id)
                )
            ).all()
        )
        if rows
        else {}
    )
    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": c.id,
                "title": c.title,
                "source": c.source,
                "url": c.url,
                "mine": c.visibility == "private",
                "item_count": item_counts.get(c.id, 0),
                "created_at": c.created_at,
            }
            for c in rows
        ],
    }


@router.get("/{content_id}")
async def get_ready_content(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    content = await db.get(Content, content_id)
    if (
        content is None
        or content.status != "ready"
        or (
            content.visibility == "private"
            and (
                await db.execute(
                    select(func.count())
                    .select_from(Content)
                    .where(
                        Content.id == content_id,
                        Content.id.in_(subscribed_content_ids(user.id)),
                    )
                )
            ).scalar_one()
            == 0
        )
    ):
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
    return {
        "id": content.id,
        "title": content.title,
        "source": content.source,
        "url": content.url,
        "mine": content.visibility == "private",
        "youtube_video_id": content.youtube_video_id,
        "segments": [
            {
                "seq": s.seq,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "en_text": s.en_text,
                "ko_text": s.ko_text,
            }
            for s in segments
        ],
    }
