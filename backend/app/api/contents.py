"""학습자용 콘텐츠 라이브러리 (읽기 전용, ready 콘텐츠만).

노출: 공용(public) 전체 + 내 개인(private) 콘텐츠 (docs/specs/content-pipeline.md).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import (
    Content,
    ContentRequest,
    ContentSubscription,
    ItemOccurrence,
    TranscriptSegment,
    User,
)
from app.services.content_difficulty import difficulty_by_content, known_ratio_by_content
from app.services.visibility import subscribed_content_ids

router = APIRouter(prefix="/contents", tags=["contents"])


def visible_content_clause(user_id: int):
    return or_(
        Content.visibility == "public",
        and_(
            Content.visibility == "private",
            Content.id.in_(subscribed_content_ids(user_id)),
        ),
        # 내 chat 덱(내가 쓰는 말)은 빼기(구독 해지) 뒤에도 목록에 남는다 —
        # 문서함 재담기 진입점 보존 (docs/specs/my-phrases.md 담기/빼기)
        and_(Content.source == "chat", Content.created_by == user_id),
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
    # 담기 전에 수준을 보여주는 파생값 — 저장 컬럼 없이 일괄 집계 (content-governance.md)
    content_ids = [c.id for c in rows]
    difficulty = await difficulty_by_content(db, content_ids)
    known_ratio = await known_ratio_by_content(db, user.id, content_ids, item_counts)
    # 담기 버튼 상태 — 담은 콘텐츠만 학습 큐에 편입된다 (content-governance.md)
    subscribed = set(
        (
            await db.execute(
                select(ContentSubscription.content_id).where(
                    ContentSubscription.user_id == user.id,
                    ContentSubscription.content_id.in_([c.id for c in rows] or [0]),
                )
            )
        )
        .scalars()
        .all()
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
                "lang": c.lang,
                # 내가 쓰는 말 전용 섹션의 편집 링크(legacy/언어별) 분기용
                "chat_kind": c.chat_kind,
                "mine": c.visibility == "private",
                "subscribed": c.id in subscribed,
                # CC 배지·저작자표시용 (consult-brief §5 — 라이선스 명칭 표시 요건)
                "youtube_license": c.youtube_license,
                # 카드 썸네일용 (cake-benchmark P1 — 썸네일 전면화)
                "youtube_video_id": c.youtube_video_id,
                "item_count": item_counts.get(c.id, 0),
                "difficulty": difficulty.get(c.id),
                "known_ratio": known_ratio.get(c.id),
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
    subscribed = (
        await db.execute(
            select(ContentSubscription.id).where(
                ContentSubscription.content_id == content_id,
                ContentSubscription.user_id == user.id,
            )
        )
    ).scalar_one_or_none() is not None
    return {
        "id": content.id,
        "title": content.title,
        "source": content.source,
        "url": content.url,
        "lang": content.lang,
        "mine": content.visibility == "private",
        "subscribed": subscribed,
        "youtube_license": content.youtube_license,
        "youtube_video_id": content.youtube_video_id,
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
    }


class ContentRequestBody(BaseModel):
    text: str = Field(min_length=2, max_length=300)


REQUESTS_PER_DAY = 5


@router.post("/requests")
async def create_content_request(
    body: ContentRequestBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """ "이런 영상이 보고 싶어요" — 공급을 수요와 연결 (effectiveness-audit P0-3).

    관리자가 백오피스 등록 화면에서 목록을 보고 CC 검색으로 채운다.
    하루 5건 제한 — 남용 가드.
    """
    from datetime import UTC, datetime, timedelta, timezone

    kst = timezone(timedelta(hours=9))
    day_start = (
        datetime.now(UTC).astimezone(kst).replace(hour=0, minute=0, second=0, microsecond=0)
    ).astimezone(UTC)
    today_count = (
        await db.execute(
            select(func.count(ContentRequest.id)).where(
                ContentRequest.user_id == user.id, ContentRequest.created_at >= day_start
            )
        )
    ).scalar_one()
    if today_count >= REQUESTS_PER_DAY:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "daily_request_limit")

    db.add(ContentRequest(user_id=user.id, text=body.text.strip()))
    await db.commit()
    return {"saved": True}
