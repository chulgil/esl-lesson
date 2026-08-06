"""학습 API — FSRS 큐/채점/통계 (docs/specs/learning.md)."""

import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import (
    Content,
    ItemOccurrence,
    LearningItem,
    PushSubscription,
    ReviewCard,
    ReviewLog,
    ThemeRewardRule,
    TranscriptSegment,
    User,
    UserSettings,
)
from app.models.item import ITEM_TYPE_LEVEL
from app.services import (
    achievements,
    embeddings,
    fsrs_service,
    insights,
    progress,
    quiz,
    retention,
    vocab_network,
)
from app.services.theme_rewards import sync_theme_rewards
from app.services.visibility import subscribed_content_ids, visible_item_clause

logger = logging.getLogger(__name__)

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


def content_item_clause(content_id: int):
    """덱 필터 — 이 콘텐츠에 등장하는 항목만 (item_occurrences 다대다, study-decks.md)."""
    return LearningItem.id.in_(
        select(ItemOccurrence.item_id).where(ItemOccurrence.content_id == content_id)
    )


@router.get("/queue")
async def get_queue(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    content_id: int | None = None,
    mode: str | None = None,
) -> dict:
    now = datetime.now(UTC)
    day_start = kst_day_start(now)
    settings = await get_user_settings(db, user)
    types = enabled_types(settings)

    # 덱 한정 학습 — 구독한 콘텐츠만, 비구독은 존재 여부도 흘리지 않는 404 (my_contents 와 동일)
    deck = None
    deck_scope = []
    if content_id is not None:
        from app.api.my_contents import get_subscribed_content

        content = await get_subscribed_content(db, content_id, user)
        deck = {"content_id": content.id, "title": content.title}
        deck_scope = [content_item_clause(content.id)]

    if not types:
        return {"questions": [], "total_due": 0, "introduced_today": 0, "deck": deck}

    # 오답 정리 모드 — 최근 오답 카드만, 신규 도입 없음. 덱과 조합 가능
    # (content_id 지정 시 덱 필터·구독 404 게이트가 위에서 이미 적용됨)
    if mode == "weak":
        weak = await progress.weak_cards(
            db, user.id, types, now, limit=QUEUE_PAGE_SIZE, extra=tuple(deck_scope)
        )
        questions = await _build_questions(db, weak, user.id)
        await db.commit()
        return {
            "total_due": len(weak),
            "introduced_today": 0,
            "hint_delay_seconds": settings.hint_delay_seconds,
            "deck": deck,
            "mode": "weak",
            "questions": questions,
        }

    reviews_today = (
        await db.execute(
            select(func.count(ReviewLog.id)).where(
                ReviewLog.user_id == user.id, ReviewLog.reviewed_at >= day_start
            )
        )
    ).scalar_one()

    review_budget = max(0, settings.daily_review_limit - reviews_today)

    async def fetch_due_cards() -> list[ReviewCard]:
        return list(
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
                        *deck_scope,
                    )
                    .order_by(ReviewCard.due_at)
                    .limit(review_budget)
                )
            ).scalars()
        )

    due_cards = await fetch_due_cards()

    # 오늘 만난 카드 = 현재 가시(구독 중)인 것만 예산에 계산 — 담기 A 로 한도를
    # 쓰고 A 를 뺀 뒤 B 를 담으면, A 의 숨은 카드가 예산을 잠근 채 due 도 0 이라
    # "복습할 카드가 없어요"가 됐다 (2026-07-30 보고). 재담기 시에는 그 카드들이
    # 다시 가시가 되어 예산에 복귀하므로 중복 편입도 없다.
    introduced_today = (
        await db.execute(
            select(func.count(ReviewCard.id))
            .join(LearningItem, LearningItem.id == ReviewCard.item_id)
            .where(
                ReviewCard.user_id == user.id,
                ReviewCard.created_at >= day_start,
                visible_item_clause(user.id),
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
                        *deck_scope,
                    )
                    .order_by(LearningItem.id.desc())
                    .limit(new_budget)
                )
            )
            .scalars()
            .all()
        )
        # 같은 레벨 안에서는 음성 연계(원어민 발화 구간) 항목 우선 — 첫 세션에
        # "듣는 카드"가 반드시 섞이게, 차별점을 운이 아니라 설계로
        # (effectiveness-audit-2026-08.md P0-1 아하 모먼트)
        playable_ids: set[int] = set()
        if fresh_items:
            playable_ids = set(
                (
                    await db.execute(
                        select(ItemOccurrence.item_id)
                        .join(Content, Content.id == ItemOccurrence.content_id)
                        .join(
                            TranscriptSegment,
                            TranscriptSegment.id == ItemOccurrence.segment_id,
                        )
                        .where(
                            ItemOccurrence.item_id.in_([i.id for i in fresh_items]),
                            Content.youtube_video_id.is_not(None),
                            TranscriptSegment.start_ms.is_not(None),
                        )
                    )
                ).scalars()
            )

        # 레벨 낮은 타입 우선 도입 (docs/specs/learning.md)
        for item in sorted(
            fresh_items,
            key=lambda i: (ITEM_TYPE_LEVEL[i.item_type], i.id not in playable_ids, -i.id),
        ):
            card = ReviewCard(user_id=user.id, item_id=item.id, state="new", due_at=now)
            db.add(card)
            new_cards.append(card)
        try:
            await db.flush()
        except IntegrityError:
            # 동시 요청(중복 탭)이 같은 항목을 먼저 도입 (uq_cards_user_item)
            # — 이번 응답은 due 카드만 반환, 신규는 승자 쪽 응답에 실림.
            # rollback 이 user/settings/due 인스턴스를 전부 만료시키므로
            # 재로드 후 재조회 (2026-08-05 스윕 — MissingGreenlet 방지)
            await db.rollback()
            new_cards = []
            await db.refresh(user)
            await db.refresh(settings)
            due_cards = await fetch_due_cards()

    ordered = due_cards + new_cards
    page = ordered[:QUEUE_PAGE_SIZE]
    questions = await _build_questions(db, page, user.id)
    await db.commit()
    return {
        "total_due": len(due_cards),
        "introduced_today": introduced_today + len(new_cards),
        "hint_delay_seconds": settings.hint_delay_seconds,
        "deck": deck,
        "questions": questions,
    }


@router.get("/decks")
async def get_decks(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """덱 카운트 — 덱 = 담은 콘텐츠 1개 (docs/specs/study-decks.md).

    같은 항목이 두 콘텐츠에 등장하면 양쪽 덱에 모두 집계된다 (다대다 — Anki 와
    다른 점). 카운트는 모두 가시성 규칙을 통과한 항목만 — 구독 해제하면 덱과
    함께 사라지고, 다시 담으면 카드 진행 상태 그대로 복귀한다.
    """
    now = datetime.now(UTC)
    contents = (
        await db.execute(
            select(Content.id, Content.title).where(Content.id.in_(subscribed_content_ids(user.id)))
        )
    ).all()
    if not contents:
        return {"items": []}
    ids = [c.id for c in contents]

    # 같은 항목이 한 콘텐츠에 여러 세그먼트로 등장할 수 있어 카드/항목 기준 distinct
    card_count = func.count(func.distinct(ReviewCard.id))
    my_cards = select(ReviewCard.item_id).where(ReviewCard.user_id == user.id)
    due_by_content = dict(
        (
            await db.execute(
                select(ItemOccurrence.content_id, card_count)
                .join(ReviewCard, ReviewCard.item_id == ItemOccurrence.item_id)
                .join(LearningItem, LearningItem.id == ItemOccurrence.item_id)
                .where(
                    ItemOccurrence.content_id.in_(ids),
                    ReviewCard.user_id == user.id,
                    ReviewCard.due_at <= now,
                    ReviewCard.suspended.is_(False),
                    visible_item_clause(user.id),
                )
                .group_by(ItemOccurrence.content_id)
            )
        ).all()
    )
    total_by_content = dict(
        (
            await db.execute(
                select(ItemOccurrence.content_id, card_count)
                .join(ReviewCard, ReviewCard.item_id == ItemOccurrence.item_id)
                .join(LearningItem, LearningItem.id == ItemOccurrence.item_id)
                .where(
                    ItemOccurrence.content_id.in_(ids),
                    ReviewCard.user_id == user.id,
                    visible_item_clause(user.id),
                )
                .group_by(ItemOccurrence.content_id)
            )
        ).all()
    )
    new_by_content = dict(
        (
            await db.execute(
                select(ItemOccurrence.content_id, func.count(func.distinct(ItemOccurrence.item_id)))
                .join(LearningItem, LearningItem.id == ItemOccurrence.item_id)
                .where(
                    ItemOccurrence.content_id.in_(ids),
                    LearningItem.id.not_in(my_cards),
                    visible_item_clause(user.id),
                )
                .group_by(ItemOccurrence.content_id)
            )
        ).all()
    )

    # 루틴 진행(0~6) — 시작한 "갈아 넣기" 여정을 덱에서 상기시킨다
    # (effectiveness-audit 2차: 라이브러리 상세에만 있으면 잊힌다)
    from app.models import ContentRoutineProgress

    routine_by_content = dict(
        (
            await db.execute(
                select(ContentRoutineProgress.content_id, func.count(ContentRoutineProgress.id))
                .where(
                    ContentRoutineProgress.user_id == user.id,
                    ContentRoutineProgress.content_id.in_(ids),
                )
                .group_by(ContentRoutineProgress.content_id)
            )
        ).all()
    )

    items = [
        {
            "content_id": cid,
            "title": title,
            "due": due_by_content.get(cid, 0),
            "new_available": new_by_content.get(cid, 0),
            "total_cards": total_by_content.get(cid, 0),
            "routine_done": routine_by_content.get(cid, 0),
        }
        for cid, title in contents
    ]
    items.sort(key=lambda d: (-d["due"], d["title"]))
    return {"items": items}


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

    # 직전 등급 — 힌트 정책 분기 재료 (2026-08-05: 쉬움(4)만 시간차 힌트,
    # 처음 학습/다시/어려움/알맞음은 순차 힌트 — learning.md 힌트 타이머)
    last_rating: dict[int, int] = {}
    rating_rows = await db.execute(
        select(ReviewLog.card_id, ReviewLog.rating)
        .where(ReviewLog.card_id.in_([c.id for c in cards]))
        .order_by(ReviewLog.card_id, ReviewLog.id.desc())
    )
    for cid, rating in rating_rows:
        if cid not in last_rating:
            last_rating[cid] = rating

    # P2: 임베딩 최근접 유사단어를 오답 선지에 우선 배치 (실패 시 랜덤 폴백)
    similar_by_item: dict[int, list[dict]] = {}
    if embeddings.enabled(db):
        for item_id, it in items_by_id.items():
            if it.item_type not in ("word", "idiom"):
                continue
            try:
                similar_by_item[item_id] = await embeddings.similar_items(db, item_id, k=5)
            except Exception:
                logger.exception("similar_items failed item=%s", item_id)
                break

    questions = []
    for card in cards:
        item = items_by_id.get(card.item_id)
        if item is None:
            continue
        question = quiz.build_question(
            item, pools[item.item_type], similar_by_item.get(card.item_id)
        )
        questions.append(
            {
                "card_id": card.id,
                "item_id": item.id,
                "state": card.state,
                "last_rating": last_rating.get(card.id),
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


@router.get("/items/{item_id}/insight")
async def item_insight(
    item_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """단어 인사이트 — 최초 조회 시 LLM 생성 후 캐시 (docs/proposal/word-insight.md)."""
    # 내게 보이는 항목만 — 구독 해제/타인 개인 항목의 인사이트 조회·LLM 생성 차단
    # (try 밖에서 검사: 아래 except Exception 이 404 를 502 로 삼키지 않도록)
    item_visible = (
        await db.execute(
            select(LearningItem.id).where(LearningItem.id == item_id, visible_item_clause(user.id))
        )
    ).scalar_one_or_none()
    if item_visible is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item_not_found")
    try:
        payload = await insights.get_or_generate(db, item_id)
    except Exception as exc:  # 생성 실패는 일시 오류 — 클라이언트 재시도 유도
        logger.exception("insight generation failed item=%s", item_id)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "insight_generation_failed") from exc
    if payload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item_not_found")
    return payload


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
    stability_before = card.stability
    meta = fsrs_service.apply_review(card, rating, settings.desired_retention, now)
    fsrs_service.set_fast_streak(card, new_streak)
    # 장기 기억 임계 교차 — 피드백 마이크로 보상 (user-journey-motivation P0 ①)
    long_term_reached = fsrs_service.crossed_long_term(stability_before, card.stability, correct)

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

    # P2: 오답이 임베딩 유사단어였는지 판정 — "아깝다" 비교 카드 (word-insight.md)
    close_match = None
    if (
        not correct
        and body.quiz_mode in ("choice_en2ko", "choice_ko2en", "cloze")
        and embeddings.enabled(db)
    ):
        field = "ko_text" if body.quiz_mode == "choice_en2ko" else "en_text"
        normalized = body.answer.strip().lower()
        try:
            for s in await embeddings.similar_items(db, item.id, k=5):
                if s[field].strip().lower() == normalized:
                    close_match = {
                        "item_id": s["id"],
                        "en_text": s["en_text"],
                        "ko_text": s["ko_text"],
                    }
                    break
        except Exception:  # 판정 실패는 기능 저하일 뿐 — 채점 응답은 정상 진행
            logger.exception("close-match check failed item=%s", item.id)

    return {
        "correct": correct,
        "rating_applied": rating,
        "long_term_reached": long_term_reached,
        "interval_previews": {str(k): round(v, 1) for k, v in previews.items()},
        "correct_answer": _correct_answer(item, body.quiz_mode),
        "close_match": close_match,
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
    user_settings = await get_user_settings(db, user)

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

    # 내일 예고 — 아직 due 아니지만 내일(KST) 안에 due 가 되는 카드 (예측 가능성,
    # user-journey-motivation P1: 세션 완료 화면 "내일 M개 예정")
    due_tomorrow = (
        await db.execute(
            select(func.count(ReviewCard.id))
            .join(LearningItem, LearningItem.id == ReviewCard.item_id)
            .where(
                ReviewCard.user_id == user.id,
                ReviewCard.due_at > now,
                ReviewCard.due_at <= day_start + timedelta(days=2),
                ReviewCard.suspended.is_(False),
                visible_item_clause(user.id),
            )
        )
    ).scalar_one()

    # 분자 = 한 번이라도 푼 카드 (reps > 0). 큐가 도입만 한 새 카드를 세면 담은
    # 콘텐츠를 꺼내보는 순간 영구 100% 가 되어 "만난 카드" 지표가 죽는다 (2026-08-03).
    # suspended 제외 — 사용자가 뺀 항목은 세지 않는다.
    # 구독 해제 항목도 제외 — 분모(visible)와 같은 규칙이라 진행률이 100%를 넘지 않는다
    level_rows = (
        await db.execute(
            select(LearningItem.item_type, func.count(ReviewCard.id))
            .join(ReviewCard, ReviewCard.item_id == LearningItem.id)
            .where(
                ReviewCard.user_id == user.id,
                ReviewCard.suspended.is_(False),
                ReviewCard.reps > 0,
                visible_item_clause(user.id),
            )
            .group_by(LearningItem.item_type)
        )
    ).all()
    cards_by_type = dict(level_rows)
    # 분모 = 내가 만날 수 있는 항목 — 큐 도입 규칙(visible_item_clause)과 동일.
    # 전역 approved 카운트는 내 개인 pending 누락/타인 개인 포함으로 부정확 (2026-07-15 검증)
    available_rows = (
        await db.execute(
            select(LearningItem.item_type, func.count(LearningItem.id))
            .where(visible_item_clause(user.id))
            .group_by(LearningItem.item_type)
        )
    ).all()
    available_by_type = dict(available_rows)

    # 잔디는 GitHub 식 1년(53주) 뷰 — 화면이 요구하는 만큼 내려준다 (2026-08-03).
    # 여유 400일: 53주 그리드가 오늘이 속한 주의 토요일까지 채워지므로 371일 + 마진
    recent = (
        await db.execute(
            select(ReviewLog.reviewed_at).where(
                ReviewLog.user_id == user.id,
                ReviewLog.reviewed_at >= now - timedelta(days=400),
            )
        )
    ).scalars()
    daily: dict[str, int] = {}
    for reviewed_at in recent:
        key = reviewed_at.astimezone(KST).date().isoformat()
        daily[key] = daily.get(key, 0) + 1

    # 책갈피(스트릭 보호) — 목표 달성 시 지급(주 1회), 공백은 자동 소모로 이어붙임
    today = now.astimezone(KST).date()
    if retention.try_award_saver(user_settings, reviews_today, today):
        await db.commit()
    streak, saved_days = await retention.streak_with_savers(
        db, user.id, user_settings, daily, today
    )

    # XP·레벨 — 산출은 services/progress.total_xp (XP 상점과 공용, 2026-08-05 이관)
    xp = await progress.total_xp(db, user.id)

    # 오답 정리 수 + 장기 기억 — 개인화 학습과학 팩 (services/progress.py)
    types = enabled_types(user_settings)
    weak_count = await progress.weak_count(db, user.id, types, now)
    long_term = await progress.long_term_stats(db, user.id, now)

    return {
        "xp": xp,
        "level": xp // 500 + 1,
        "level_progress": (xp % 500) / 500,
        "weak_count": weak_count,
        "long_term": long_term,
        "due_count": due_count,
        "due_tomorrow": due_tomorrow,
        "reviews_today": reviews_today,
        "daily_goal": user_settings.daily_goal,
        "streak_days": streak,
        "streak_savers": user_settings.streak_savers,
        "streak_saved_days": saved_days,
        "levels": [
            {
                "level": level,
                "item_type": item_type,
                "cards": cards_by_type.get(item_type, 0),
                "available_items": available_by_type.get(item_type, 0),
            }
            for item_type, level in ITEM_TYPE_LEVEL.items()
        ],
        "daily": daily,
    }


@router.get("/achievements")
async def get_achievements(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """업적 배지 — 로그 실시간 집계, 소급 반영 (P3 리텐션)."""
    # 학습 홈 방문 = 보상 지급 접점 — 달성 즉시 다음 방문에서 테마가 열린다
    await sync_theme_rewards(db, user.id)
    items = await achievements.compute(db, user.id)
    # 보상 테마 예고 — 스티커에 "보상: 캔디 테마" 칩 (theme-mall.md)
    rules = (await db.execute(select(ThemeRewardRule))).scalars().all()
    reward_by_key = {r.achievement_key: r.theme_key for r in rules}
    items = [{**a, "reward_theme": reward_by_key.get(a["key"])} for a in items]
    return {
        "items": items,
        "achieved_count": sum(1 for a in items if a["achieved"]),
        "total": len(items),
    }


@router.get("/quests")
async def get_quests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """오늘의 미션 3종 — 날짜 결정적 로테이션, 완료는 원장에 멱등 적립.

    진행도는 기존 로그에서 파생 (docs/proposal/retention-plan.md).
    """
    return await retention.compute_quests(db, user.id)


@router.get("/leaderboard")
async def study_leaderboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """주간 학습 리더보드 — 나 + 수락된 친구의 최근 7일 복습 수 (P1 데일리 루프).

    0건 친구도 표시한다 — "친구가 아직 0개"가 곧 동기부여라서.
    """
    from sqlalchemy import and_, or_

    from app.models.friend import Friendship

    friend_rows = (
        (
            await db.execute(
                select(Friendship).where(
                    Friendship.status == "accepted",
                    or_(
                        Friendship.requester_id == user.id,
                        Friendship.addressee_id == user.id,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    ids = {user.id} | {
        r.addressee_id if r.requester_id == user.id else r.requester_id for r in friend_rows
    }
    since = datetime.now(UTC) - timedelta(days=7)
    rows = (
        await db.execute(
            select(User.id, User.nickname, func.count(ReviewLog.id))
            .join(
                ReviewLog,
                and_(ReviewLog.user_id == User.id, ReviewLog.reviewed_at >= since),
                isouter=True,
            )
            .where(User.id.in_(ids))
            .group_by(User.id, User.nickname)
            .order_by(func.count(ReviewLog.id).desc(), User.nickname)
        )
    ).all()

    items = []
    prev_count: int | None = None
    prev_rank = 0
    for i, (uid, name, count) in enumerate(rows, start=1):
        rank = prev_rank if count == prev_count else i
        items.append(
            {
                "user_id": uid,
                "name": name,
                "reviews": count,
                "rank": rank,
                "me": uid == user.id,
            }
        )
        prev_count, prev_rank = count, rank
    return {"items": items}


MAX_NETWORK_NODES = 300


@router.get("/network")
async def get_network(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """어휘망 그래프 — 내 단어·숙어 카드 노드 + 임베딩 근접 엣지 + 덱 밖 추천 (P3)."""
    rows = (
        await db.execute(
            select(ReviewCard, LearningItem)
            .join(LearningItem, LearningItem.id == ReviewCard.item_id)
            .where(
                ReviewCard.user_id == user.id,
                ReviewCard.suspended.is_(False),
                # 구독 해제한 콘텐츠의 단어는 노드에서 제외 — 카드는 보존되므로
                # 다시 담으면 그대로 복귀한다 (content-governance.md 가시성 규칙)
                visible_item_clause(user.id),
                LearningItem.item_type.in_(("word", "idiom")),
            )
            .order_by(ReviewCard.created_at.desc(), ReviewCard.id.desc())
            .limit(MAX_NETWORK_NODES)
        )
    ).all()
    nodes = [
        {
            "item_id": item.id,
            "en": item.en_text,
            "ko": item.ko_text,
            "item_type": item.item_type,
            "state": card.state,
            "reps": card.reps,
        }
        for card, item in rows
    ]

    edges: list[dict] = []
    suggestions: list[dict] = []
    enabled = embeddings.enabled(db)
    if enabled and nodes:
        try:
            my_ids = [n["item_id"] for n in nodes]
            neighbor = await vocab_network.neighbor_rows(db, my_ids)
            edges, candidates = vocab_network.build_network(set(my_ids), neighbor)
            if candidates:
                # 추천은 내 덱 밖 항목 — 가시성 규칙(공용 승인 ∪ 내 개인) 통과분만
                visible = set(
                    (
                        await db.execute(
                            select(LearningItem.id).where(
                                LearningItem.id.in_([c["item_id"] for c in candidates]),
                                visible_item_clause(user.id),
                            )
                        )
                    ).scalars()
                )
                suggestions = [c for c in candidates if c["item_id"] in visible]
        except Exception:
            logger.exception("vocab network failed user=%s", user.id)
            edges, suggestions = [], []

    return {
        "nodes": nodes,
        "edges": edges,
        "suggestions": suggestions,
        "embeddings_enabled": enabled,
    }


async def _load_card(db: AsyncSession, card_id: int, user: User) -> ReviewCard:
    card = await db.get(ReviewCard, card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "card not found")
    return card


class SuspendBody(BaseModel):
    suspended: bool


class AddCardBody(BaseModel):
    item_id: int


@cards_router.post("")
async def add_card(
    body: AddCardBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """유사단어 원탭 학습 추가 (P3) — 이미 있으면 기존 카드 반환."""
    item = (
        await db.execute(
            select(LearningItem).where(
                LearningItem.id == body.item_id,
                LearningItem.review_status == "approved",
                visible_item_clause(user.id),
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item_not_found")
    existing = (
        await db.execute(
            select(ReviewCard).where(
                ReviewCard.user_id == user.id, ReviewCard.item_id == body.item_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {"added": False, "card_id": existing.id}
    uid = user.id  # rollback 은 ORM 객체를 만료시킨다 — 값으로 캡처
    card = ReviewCard(user_id=uid, item_id=body.item_id, state="new", due_at=datetime.now(UTC))
    db.add(card)
    try:
        await db.commit()
    except IntegrityError:
        # 동시 추가 경합 (uq_cards_user_item) — 먼저 저장된 카드를 채택
        await db.rollback()
        winner = (
            await db.execute(
                select(ReviewCard).where(
                    ReviewCard.user_id == uid, ReviewCard.item_id == body.item_id
                )
            )
        ).scalar_one()
        return {"added": False, "card_id": winner.id}
    return {"added": True, "card_id": card.id}


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
    daily_goal: int | None = Field(default=None, ge=5, le=200)
    desired_retention: float | None = Field(default=None, ge=0.7, le=0.97)
    hint_delay_seconds: int | None = Field(default=None, ge=0, le=120)
    # 복습 리마인더 시각(KST) — 새벽(5시 미만) 금지, 실행 의도 (push-reminder.md)
    reminder_hour: int | None = Field(default=None, ge=5, le=23)
    study_level: int | None = Field(default=None, ge=1, le=4)
    levels_enabled: list[int] | None = None


@settings_router.get("")
async def read_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    settings = await get_user_settings(db, user)
    await db.commit()
    return _settings_dict(settings, await _push_subscribed(db, user.id))


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
    fields = (
        "daily_new_limit",
        "daily_review_limit",
        "daily_goal",
        "desired_retention",
        "hint_delay_seconds",
        "reminder_hour",
    )
    for field in fields:
        value = getattr(body, field)
        if value is not None:
            setattr(settings, field, value)
    await db.commit()
    return _settings_dict(settings, await _push_subscribed(db, user.id))


async def _push_subscribed(db: AsyncSession, user_id: int) -> bool:
    """이 유저의 기기 중 하나라도 푸시 구독이 살아 있는가 — 온보딩 체크리스트
    ③ 리마인더 설정 완료 판정 (docs/proposal/effectiveness-audit-2026-08.md 구멍 4).
    구독 행은 기기당 1개라 존재 여부만 보면 된다."""
    row = await db.execute(
        select(PushSubscription.id).where(PushSubscription.user_id == user_id).limit(1)
    )
    return row.scalar_one_or_none() is not None


def _settings_dict(settings: UserSettings, push_subscribed: bool) -> dict:
    return {
        "daily_new_limit": settings.daily_new_limit,
        "daily_review_limit": settings.daily_review_limit,
        "daily_goal": settings.daily_goal,
        "desired_retention": settings.desired_retention,
        "hint_delay_seconds": settings.hint_delay_seconds,
        "reminder_hour": settings.reminder_hour,
        "study_level": settings.study_level,
        "levels_enabled": settings.levels_enabled,
        "push_subscribed": push_subscribed,
    }
