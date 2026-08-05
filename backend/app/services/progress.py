"""학습 진행 지표 — 오답 정리(weak) 선정 + 장기 기억(long-term) 산출.

기획: docs/proposal/duolingo-benchmark-2026-08.md / 스펙: docs/specs/learning.md
api/study.py 에서 분리 (2026-08-05 유지보수 리팩토링) — 선정·산출 규칙의 정본.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearningItem, ReviewCard, ReviewLog
from app.services.fsrs_service import LONG_TERM_STABILITY_DAYS
from app.services.visibility import visible_item_clause

KST = timezone(timedelta(hours=9))
WEAK_WINDOW_DAYS = 7  # 오답 정리 — 최근 오답 창(일)
LONG_TERM_WEEKS = 8  # 장기 기억 추이 창(주)


def weak_filter(user_id: int, types: list[str], now: datetime, extra: tuple = ()):
    """오답 정리 대상 — 최근 창 내 오답 이력 + 가시성 + 활성 타입 (suspended 제외).

    extra 로 덱 한정 등 추가 조건을 합성한다 (learning.md 오답 정리 모드).
    """
    wrong_recent = select(ReviewLog.card_id).where(
        ReviewLog.user_id == user_id,
        ReviewLog.correct.is_(False),
        ReviewLog.reviewed_at >= now - timedelta(days=WEAK_WINDOW_DAYS),
    )
    return (
        ReviewCard.user_id == user_id,
        ReviewCard.suspended.is_(False),
        ReviewCard.id.in_(wrong_recent),
        visible_item_clause(user_id),
        LearningItem.item_type.in_(types),
        *extra,
    )


async def weak_cards(
    db: AsyncSession,
    user_id: int,
    types: list[str],
    now: datetime,
    limit: int,
    extra: tuple = (),
) -> list[ReviewCard]:
    if not types:
        return []
    return list(
        (
            await db.execute(
                select(ReviewCard)
                .join(LearningItem, LearningItem.id == ReviewCard.item_id)
                .where(*weak_filter(user_id, types, now, extra))
                # stability 낮은 순, NULL(추정 전 = 가장 흔들림) 최우선
                .order_by(ReviewCard.stability.asc().nulls_first(), ReviewCard.id)
                .limit(limit)
            )
        ).scalars()
    )


async def weak_count(db: AsyncSession, user_id: int, types: list[str], now: datetime) -> int:
    if not types:
        return 0
    return (
        await db.execute(
            select(func.count(func.distinct(ReviewCard.id)))
            .join(LearningItem, LearningItem.id == ReviewCard.item_id)
            .where(*weak_filter(user_id, types, now))
        )
    ).scalar_one()


async def long_term_stats(db: AsyncSession, user_id: int, now: datetime) -> dict:
    """장기 기억 — stability 임계 이상 카드 수 + 주별 도달 누적 (로그 재생, 소급 가능)."""
    count = (
        await db.execute(
            select(func.count(ReviewCard.id))
            .join(LearningItem, LearningItem.id == ReviewCard.item_id)
            .where(
                ReviewCard.user_id == user_id,
                ReviewCard.suspended.is_(False),
                ReviewCard.state == "review",
                ReviewCard.stability >= LONG_TERM_STABILITY_DAYS,
                visible_item_clause(user_id),
            )
        )
    ).scalar_one()

    # 카드별 "간격 7일+ 첫 도달" 시각 — 현재 가시성과 무관한 역사적 도달 기록
    reach_rows = (
        await db.execute(
            select(func.min(ReviewLog.reviewed_at))
            .where(
                ReviewLog.user_id == user_id,
                ReviewLog.scheduled_days >= LONG_TERM_STABILITY_DAYS,
            )
            .group_by(ReviewLog.card_id)
        )
    ).scalars()
    reach_dates = [r.astimezone(KST).date() for r in reach_rows]

    today = now.astimezone(KST).date()
    this_monday = today - timedelta(days=today.weekday())
    weekly = []
    for i in range(LONG_TERM_WEEKS - 1, -1, -1):
        week_start = this_monday - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        weekly.append(
            {
                "week_start": week_start.isoformat(),
                "count": sum(1 for d in reach_dates if d <= week_end),
            }
        )
    return {"count": count, "weekly": weekly}
