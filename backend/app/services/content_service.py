"""콘텐츠 등록/조회 공용 로직 — admin(공용)과 my(개인) 라우터가 공유."""

import re
from typing import Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Content,
    ExtractionJob,
    ItemOccurrence,
    LearningItem,
    ReviewCard,
    TranscriptSegment,
)
from app.services.youtube import parse_video_id


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


def split_sentences(text: str) -> list[str]:
    """수기 스크립트 문장 분리: 줄바꿈 우선, 없으면 문장부호."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]


async def create_content(
    db: AsyncSession, body: ContentCreate, creator_id: int, visibility: str
) -> Content:
    """콘텐츠 행 생성 (커밋 포함). 파이프라인 큐잉은 호출부에서."""
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
            visibility=visibility,
            youtube_video_id=video_id,
            url=body.url,
            title=body.title or f"(제목 조회 중) {video_id}",
            created_by=creator_id,
        )
        db.add(content)
        await db.commit()
        return content

    content = Content(
        source="manual",
        visibility=visibility,
        url=body.url,
        title=body.title,
        created_by=creator_id,
    )
    db.add(content)
    await db.flush()
    en_lines = split_sentences(body.script_en or "")
    for seq, line in enumerate(en_lines):
        db.add(TranscriptSegment(content_id=content.id, seq=seq, en_text=line))
    ko_lines = split_sentences(body.script_ko or "") if body.script_ko else []
    if ko_lines and len(ko_lines) == len(en_lines):
        segments = await db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.content_id == content.id)
            .order_by(TranscriptSegment.seq)
        )
        for seg, ko in zip(list(segments.scalars()), ko_lines, strict=True):
            seg.ko_text = ko
    await db.commit()
    return content


async def content_detail(db: AsyncSession, content: Content) -> dict:
    segments = (
        (
            await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.content_id == content.id)
                .order_by(TranscriptSegment.seq)
            )
        )
        .scalars()
        .all()
    )
    jobs = (
        (await db.execute(select(ExtractionJob).where(ExtractionJob.content_id == content.id)))
        .scalars()
        .all()
    )
    items = (
        await db.execute(
            select(LearningItem, ItemOccurrence)
            .join(ItemOccurrence, ItemOccurrence.item_id == LearningItem.id)
            .where(ItemOccurrence.content_id == content.id)
            .order_by(LearningItem.item_type, LearningItem.id)
        )
    ).all()
    return {
        "id": content.id,
        "source": content.source,
        "visibility": content.visibility,
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


def retry_content_row(content: Content) -> None:
    if content.status not in ("failed", "ready"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"cannot retry in {content.status}")
    content.status = "pending"
    content.error_message = None


async def delete_content_row(db: AsyncSession, content: Content) -> None:
    """콘텐츠 삭제 + 다른 출처가 없는 고아 항목 정리 (커밋 포함).

    연습 기록(review_cards)이 있는 항목은 남긴다 — 출처가 사라져 향후 학습
    목록에서는 빠지지만(가시성 규칙) 기록·통계는 보존되고, 같은 항목을
    재등록하면 FSRS 진행 상태가 그대로 이어진다.
    """
    # occurrence 는 명시 삭제 — DB cascade(postgres)에만 맡기면 sqlite 테스트와
    # 프로덕션의 고아 판정이 달라진다
    await db.execute(
        ItemOccurrence.__table__.delete().where(ItemOccurrence.content_id == content.id)
    )
    await db.delete(content)
    has_occurrence = (
        select(ItemOccurrence.id).where(ItemOccurrence.item_id == LearningItem.id).exists()
    )
    has_card = select(ReviewCard.id).where(ReviewCard.item_id == LearningItem.id).exists()
    orphans = await db.execute(select(LearningItem).where(~has_occurrence, ~has_card))
    for item in orphans.scalars():
        await db.delete(item)
    await db.commit()


def content_summary(content: Content) -> dict:
    return {
        "id": content.id,
        "source": content.source,
        "visibility": content.visibility,
        "title": content.title,
        "status": content.status,
        "youtube_video_id": content.youtube_video_id,
        "error_message": content.error_message,
        "created_at": content.created_at,
    }
