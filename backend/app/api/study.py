"""학습 API — FSRS 큐/채점/통계 (docs/specs/learning.md)."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import (
    Content,
    ItemOccurrence,
    LearningItem,
    ReviewCard,
    ReviewLog,
    TranscriptSegment,
    User,
    UserSettings,
)
from app.models.item import ITEM_TYPE_LEVEL
from app.services import fsrs_service, quiz
from app.services.visibility import visible_item_clause

router = APIRouter(prefix="/study", tags=["study"])
cards_router = APIRouter(prefix="/cards", tags=["study"])
settings_router = APIRouter(prefix="/settings", tags=["study"])

KST = timezone(timedelta(hours=9))
LEVEL_TYPES = {level: t for t, level in ITEM_TYPE_LEVEL.items()}
QUEUE_PAGE_SIZE = 20
DISTRACTOR_POOL_SIZE = 200


def kst_day_start(now: datetime) -> datetime:
    local = now.astimezone(KST)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


async def get_user_settings(db: AsyncSession, user: User) -> UserSettings:
    settings = await db.get(UserSettings, user.id)
    if settings is None:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        await db.flush()
    return settings


def enabled_types(settings: UserSettings) -> list[str]:
    return [LEVEL_TYPES[level] for level in settings.levels_enabled if level in LEVEL_TYPES]


@router.get("/queue")
async def get_queue(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    now = datetime.now(UTC)
    day_start = kst_day_start(now)
    settings = await get_user_settings(db, user)
    types = enabled_types(settings)
    if not types:
        return {"questions": [], "total_due": 0, "introduced_today": 0}

    reviews_today = (
        await db.execute(
            select(func.count(ReviewLog.id)).where(
                ReviewLog.user_id == user.id, ReviewLog.reviewed_at >= day_start
            )
        )
    ).scalar_one()

    review_budget = max(0, settings.daily_review_limit - reviews_today)
    due_cards = list(
        (
            await db.execute(
                select(ReviewCard)
                .join(LearningItem, LearningItem.id == ReviewCard.item_id)
                .where(
                    ReviewCard.user_id == user.id,
                    ReviewCard.due_at <= now,
                    ReviewCard.suspended.is_(False),
                    visible_item_clause(user.id),
                    LearningItem.item_type.in_(types),
                )
                .order_by(ReviewCard.due_at)
                .limit(review_budget)
            )
        ).scalars()
    )

    introduced_today = (
        await db.execute(
            select(func.count(ReviewCard.id)).where(
                ReviewCard.user_id == user.id, ReviewCard.created_at >= day_start
            )
        )
    ).scalar_one()
    new_budget = max(0, settings.daily_new_limit - introduced_today)
    new_cards: list[ReviewCard] = []
    if new_budget > 0:
        existing = select(ReviewCard.item_id).where(ReviewCard.user_id == user.id).scalar_subquery()
        fresh_items = (
            (
                await db.execute(
                    select(LearningItem)
                    .where(
                        visible_item_clause(user.id),
                        LearningItem.item_type.in_(types),
                        LearningItem.id.not_in(existing),
                    )
                    .order_by(LearningItem.id.desc())
                    .limit(new_budget)
                )
            )
            .scalars()
            .all()
        )
        # 레벨 낮은 타입 우선 도입 (docs/specs/learning.md)
        for item in sorted(fresh_items, key=lambda i: (ITEM_TYPE_LEVEL[i.item_type], -i.id)):
            card = ReviewCard(user_id=user.id, item_id=item.id, state="new", due_at=now)
            db.add(card)
            new_cards.append(card)
        await db.flush()

    ordered = due_cards + new_cards
    page = ordered[:QUEUE_PAGE_SIZE]
    questions = await _build_questions(db, page, user.id)
    await db.commit()
    return {
        "total_due": len(due_cards),
        "introduced_today": introduced_today + len(new_cards),
        "hint_delay_seconds": settings.hint_delay_seconds,
        "questions": questions,
    }


async def _build_questions(db: AsyncSession, cards: list[ReviewCard], user_id: int) -> list[dict]:
    if not cards:
        return []
    items = (
        (
            await db.execute(
                select(LearningItem)
                .options(selectinload(LearningItem.occurrences))
                .where(LearningItem.id.in_([c.item_id for c in cards]))
            )
        )
        .scalars()
        .all()
    )
    items_by_id = {i.id: i for i in items}
    types_needed = {i.item_type for i in items}
    pools: dict[str, list[LearningItem]] = {}
    for item_type in types_needed:
        pools[item_type] = list(
            (
                await db.execute(
                    select(LearningItem)
                    .where(
                        LearningItem.item_type == item_type,
                        visible_item_clause(user_id),
                    )
                    .limit(DISTRACTOR_POOL_SIZE)
                )
            ).scalars()
        )

    media_by_item = await _media_for_items(db, list(items_by_id.keys()))

    questions = []
    for card in cards:
        item = items_by_id.get(card.item_id)
        if item is None:
            continue
        question = quiz.build_question(item, pools[item.item_type])
        questions.append(
            {
                "card_id": card.id,
                "item_id": item.id,
                "state": card.state,
                "media": media_by_item.get(item.id),
                **question,
            }
        )
    return questions


async def _media_for_items(db: AsyncSession, item_ids: list[int]) -> dict[int, dict]:
    """항목별 출처 유튜브 구간 (학습 중 '구간 듣기' — docs/specs/learning.md)."""
    if not item_ids:
        return {}
    rows = (
        await db.execute(
            select(
                ItemOccurrence.item_id,
                Content.youtube_video_id,
                TranscriptSegment.start_ms,
                TranscriptSegment.end_ms,
            )
            .join(Content, Content.id == ItemOccurrence.content_id)
            .join(TranscriptSegment, TranscriptSegment.id == ItemOccurrence.segment_id)
            .where(
                ItemOccurrence.item_id.in_(item_ids),
                Content.youtube_video_id.is_not(None),
                TranscriptSegment.start_ms.is_not(None),
            )
        )
    ).all()
    media: dict[int, dict] = {}
    for item_id, video_id, start_ms, end_ms in rows:
        if item_id not in media:  # 첫 출처 사용
            media[item_id] = {
                "video_id": video_id,
                "start_ms": start_ms,
                "end_ms": end_ms or start_ms + 5000,
            }
    return media


class AnswerBody(BaseModel):
    card_id: int
    quiz_mode: str
    answer: str
    duration_ms: int | None = Field(default=None, ge=0, le=10 * 60 * 1000)


@router.post("/answer")
async def submit_answer(
    body: AnswerBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    card = await _load_card(db, body.card_id, user)
    item = (
        await db.execute(
            select(LearningItem)
            .options(selectinload(LearningItem.occurrences))
            .where(LearningItem.id == card.item_id)
        )
    ).scalar_one()

    try:
        correct = quiz.grade(item, body.quiz_mode, body.answer)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    settings = await get_user_settings(db, user)
    fast_streak = fsrs_service.get_fast_streak(card)
    rating, new_streak = fsrs_service.compute_rating(
        correct, body.duration_ms, body.quiz_mode, fast_streak
    )
    now = datetime.now(UTC)
    previews = fsrs_service.preview_intervals(card, settings.desired_retention, now)
    meta = fsrs_service.apply_review(card, rating, settings.desired_retention, now)
    fsrs_service.set_fast_streak(card, new_streak)

    db.add(
        ReviewLog(
            card_id=card.id,
            user_id=user.id,
            rating=rating,
            correct=correct,
            answer_text=body.answer[:2000],
            quiz_mode=body.quiz_mode,
            duration_ms=body.duration_ms,
            state_before=meta["state_before"],
            scheduled_days=meta["scheduled_days"],
            elapsed_days=meta["elapsed_days"],
            reviewed_at=now,
        )
    )
    await db.commit()

    return {
        "correct": correct,
        "rating_applied": rating,
        "interval_previews": {str(k): round(v, 1) for k, v in previews.items()},
        "correct_answer": _correct_answer(item, body.quiz_mode),
        "explanation": {
            "ko": item.ko_text,
            "thinking_ko": item.hint_thinking,
            "context_en": next((o.context_en for o in item.occurrences if o.context_en), None),
        },
        "card": {"state": card.state, "due_at": card.due_at},
    }


def _correct_answer(item: LearningItem, quiz_mode: str) -> str:
    if quiz_mode == "choice_en2ko":
        return item.ko_text
    if quiz_mode == "pattern":
        for occ in item.occurrences:
            if occ.context_en:
                return occ.context_en
    return item.en_text


class RateBody(BaseModel):
    card_id: int
    rating: int = Field(ge=1, le=4)


@router.post("/rate")
async def rate_last_review(
    body: RateBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """레벨 4 자기평가 보정: 직전 리뷰를 사용자 rating 으로 다시 스케줄링."""
    card = await _load_card(db, body.card_id, user)
    stored = card.fsrs_json or {}
    prev = stored.get("prev")
    if not prev:
        raise HTTPException(status.HTTP_409_CONFLICT, "no revisable review")

    settings = await get_user_settings(db, user)
    # 직전 스냅샷 복원 후 재적용
    card.fsrs_json = {**stored, "card": prev["card"], "prev": None}
    card.reps = prev["reps"]
    card.lapses = prev["lapses"]
    card.state = prev["state"]
    card.last_review_at = (
        datetime.fromisoformat(prev["last_review_at"]) if prev["last_review_at"] else None
    )
    fsrs_service.apply_review(card, body.rating, settings.desired_retention)

    last_log = (
        await db.execute(
            select(ReviewLog)
            .where(ReviewLog.card_id == card.id)
            .order_by(ReviewLog.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last_log:
        last_log.rating = body.rating
    await db.commit()
    return {"card": {"state": card.state, "due_at": card.due_at}, "rating_applied": body.rating}


@router.get("/stats")
async def get_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    now = datetime.now(UTC)
    day_start = kst_day_start(now)

    due_count = (
        await db.execute(
            select(func.count(ReviewCard.id))
            .join(LearningItem, LearningItem.id == ReviewCard.item_id)
            .where(
                ReviewCard.user_id == user.id,
                ReviewCard.due_at <= now,
                ReviewCard.suspended.is_(False),
                visible_item_clause(user.id),
            )
        )
    ).scalar_one()
    reviews_today = (
        await db.execute(
            select(func.count(ReviewLog.id)).where(
                ReviewLog.user_id == user.id, ReviewLog.reviewed_at >= day_start
            )
        )
    ).scalar_one()

    level_rows = (
        await db.execute(
            select(LearningItem.item_type, func.count(ReviewCard.id))
            .join(ReviewCard, ReviewCard.item_id == LearningItem.id)
            .where(ReviewCard.user_id == user.id)
            .group_by(LearningItem.item_type)
        )
    ).all()
    cards_by_type = dict(level_rows)
    approved_rows = (
        await db.execute(
            select(LearningItem.item_type, func.count(LearningItem.id))
            .where(LearningItem.review_status == "approved")
            .group_by(LearningItem.item_type)
        )
    ).all()
    approved_by_type = dict(approved_rows)

    recent = (
        await db.execute(
            select(ReviewLog.reviewed_at).where(
                ReviewLog.user_id == user.id,
                ReviewLog.reviewed_at >= now - timedelta(days=60),
            )
        )
    ).scalars()
    daily: dict[str, int] = {}
    for reviewed_at in recent:
        key = reviewed_at.astimezone(KST).date().isoformat()
        daily[key] = daily.get(key, 0) + 1

    streak = 0
    cursor = now.astimezone(KST).date()
    if daily.get(cursor.isoformat(), 0) == 0:
        cursor -= timedelta(days=1)  # 오늘 아직 안 했으면 어제부터 계산
    while daily.get(cursor.isoformat(), 0) > 0:
        streak += 1
        cursor -= timedelta(days=1)

    return {
        "due_count": due_count,
        "reviews_today": reviews_today,
        "streak_days": streak,
        "levels": [
            {
                "level": level,
                "item_type": item_type,
                "cards": cards_by_type.get(item_type, 0),
                "approved_items": approved_by_type.get(item_type, 0),
            }
            for item_type, level in ITEM_TYPE_LEVEL.items()
        ],
        "daily": daily,
    }


async def _load_card(db: AsyncSession, card_id: int, user: User) -> ReviewCard:
    card = await db.get(ReviewCard, card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "card not found")
    return card


class SuspendBody(BaseModel):
    suspended: bool


@cards_router.post("/{card_id}/suspend")
async def suspend_card(
    card_id: int,
    body: SuspendBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    card = await _load_card(db, card_id, user)
    card.suspended = body.suspended
    await db.commit()
    return {"id": card.id, "suspended": card.suspended}


class SettingsPatch(BaseModel):
    daily_new_limit: int | None = Field(default=None, ge=0, le=200)
    daily_review_limit: int | None = Field(default=None, ge=0, le=1000)
    desired_retention: float | None = Field(default=None, ge=0.7, le=0.97)
    hint_delay_seconds: int | None = Field(default=None, ge=0, le=120)
    study_level: int | None = Field(default=None, ge=1, le=4)
    levels_enabled: list[int] | None = None


@settings_router.get("")
async def read_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    settings = await get_user_settings(db, user)
    await db.commit()
    return _settings_dict(settings)


@settings_router.patch("")
async def update_settings(
    body: SettingsPatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    settings = await get_user_settings(db, user)
    if body.study_level is not None:
        # 학습 난이도 → 활성 레벨 파생 (1..study_level). 저레벨은 문장(4=타이핑) 제외
        settings.study_level = body.study_level
        settings.levels_enabled = list(range(1, body.study_level + 1))
    elif body.levels_enabled is not None:
        invalid = set(body.levels_enabled) - set(LEVEL_TYPES)
        if invalid:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"invalid levels {invalid}")
        settings.levels_enabled = sorted(set(body.levels_enabled))
    fields = ("daily_new_limit", "daily_review_limit", "desired_retention", "hint_delay_seconds")
    for field in fields:
        value = getattr(body, field)
        if value is not None:
            setattr(settings, field, value)
    await db.commit()
    return _settings_dict(settings)


def _settings_dict(settings: UserSettings) -> dict:
    return {
        "daily_new_limit": settings.daily_new_limit,
        "daily_review_limit": settings.daily_review_limit,
        "desired_retention": settings.desired_retention,
        "hint_delay_seconds": settings.hint_delay_seconds,
        "study_level": settings.study_level,
        "levels_enabled": settings.levels_enabled,
    }
