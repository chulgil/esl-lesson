"""주간 성적표 — 지난주(월~일, KST)의 나 vs 그 전주의 나 (docs/specs/weekly-report.md).

기획: docs/proposal/effectiveness-audit-2026-08.md 구멍 5 — 증거는 쌓이는데 주
단위로 돌려주지 않는다. 재료(복습·정답률·장기 기억·루틴·재청취)는 이미 전부
로그에 있으므로 **주간 집계 스냅샷 테이블을 만들지 않는다** (장기 기억 지표와
동일 원칙: 산식이 바뀌어도 과거가 소급 반영된다).
"""

from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentRoutineProgress, ListenCheck, ReviewLog, UserSettings
from app.services import progress, retention

KST = timezone(timedelta(hours=9))


def last_week_start(now: datetime) -> date:
    """성적표 대상 주의 월요일 (KST). 월요일 아침에 보는 것이 '지난주'다."""
    today = now.astimezone(KST).date()
    return today - timedelta(days=today.weekday() + 7)


def _utc_bounds(week_start: date) -> tuple[datetime, datetime]:
    """[월 00:00, 다음 월 00:00) KST 를 UTC 로 — 로그 저장 규칙(UTC)과 맞춘다."""
    start = datetime.combine(week_start, datetime.min.time(), tzinfo=KST).astimezone(UTC)
    return start, start + timedelta(days=7)


async def _review_stats(
    db: AsyncSession, user_id: int, start: datetime, end: datetime
) -> tuple[int, int]:
    """(복습 수, 정답 수) — 한 주 구간."""
    total, correct = (
        await db.execute(
            select(
                func.count(ReviewLog.id),
                func.coalesce(func.sum(case((ReviewLog.correct.is_(True), 1), else_=0)), 0),
            ).where(
                ReviewLog.user_id == user_id,
                ReviewLog.reviewed_at >= start,
                ReviewLog.reviewed_at < end,
            )
        )
    ).one()
    return int(total), int(correct)


async def _routine_steps(db: AsyncSession, user_id: int, start: datetime, end: datetime) -> int:
    """루틴 단계 완료 수 — 행 존재=완료라 created_at 이 곧 체크 시각 (content-routine.md)."""
    return (
        await db.execute(
            select(func.count(ContentRoutineProgress.id)).where(
                ContentRoutineProgress.user_id == user_id,
                ContentRoutineProgress.created_at >= start,
                ContentRoutineProgress.created_at < end,
            )
        )
    ).scalar_one()


async def _listen_delta(
    db: AsyncSession, user_id: int, start: datetime, end: datetime
) -> dict | None:
    """재청취 이해도 델타 — 지난주에 '루틴 후'(stage 2)를 찍은 콘텐츠의 전후 평균 차.

    stage 2 시점으로 주를 가른다 — 전후 비교가 **완성된 순간**이 그 주의 증거다.
    전(stage 1)이 없는 콘텐츠는 비교 불가라 제외, 남는 게 없으면 None (카드에서 숨김).
    """
    after_rows = (
        await db.execute(
            select(ListenCheck.content_id, ListenCheck.score).where(
                ListenCheck.user_id == user_id,
                ListenCheck.stage == 2,
                ListenCheck.created_at >= start,
                ListenCheck.created_at < end,
            )
        )
    ).all()
    if not after_rows:
        return None

    before = dict(
        (
            await db.execute(
                select(ListenCheck.content_id, ListenCheck.score).where(
                    ListenCheck.user_id == user_id,
                    ListenCheck.stage == 1,
                    ListenCheck.content_id.in_([cid for cid, _ in after_rows]),
                )
            )
        ).all()
    )
    deltas = [score - before[cid] for cid, score in after_rows if cid in before]
    if not deltas:
        return None
    return {"delta": round(sum(deltas) / len(deltas), 1), "contents": len(deltas)}


async def _streak_days(
    db: AsyncSession, user_id: int, settings: UserSettings, now: datetime
) -> int:
    """스트릭 — stats 와 같은 파생(책갈피 자동 소모 포함)을 재사용해 수치를 일치시킨다."""
    today = now.astimezone(KST).date()
    since = now - timedelta(days=retention.STREAK_WINDOW_DAYS)
    recent = (
        await db.execute(
            select(ReviewLog.reviewed_at).where(
                ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= since
            )
        )
    ).scalars()
    daily: dict[str, int] = {}
    for reviewed_at in recent:
        key = reviewed_at.astimezone(KST).date().isoformat()
        daily[key] = daily.get(key, 0) + 1
    streak, _ = await retention.streak_with_savers(db, user_id, settings, daily, today)
    return streak


async def review_counts(
    db: AsyncSession, user_id: int, now: datetime | None = None
) -> tuple[int, int]:
    """(지난주 복습 수, 그 전주 복습 수) — 푸시 게이트·문구용 경량 조회."""
    now = now or datetime.now(UTC)
    start, end = _utc_bounds(last_week_start(now))
    last, _ = await _review_stats(db, user_id, start, end)
    prev, _ = await _review_stats(db, user_id, start - timedelta(days=7), start)
    return last, prev


async def build(
    db: AsyncSession, user_id: int, settings: UserSettings, now: datetime | None = None
) -> dict:
    """지난주 성적표 — 전부 델타 동반 (절대치보다 변화가 읽힌다).

    데이터가 전무한 신규 사용자도 0/None 으로 안전하게 채워진다 —
    `has_data`(지난주 복습 1개 이상)가 노출 게이트.
    """
    now = now or datetime.now(UTC)
    week_start = last_week_start(now)
    week_end = week_start + timedelta(days=6)
    prev_week_start = week_start - timedelta(days=7)
    start, end = _utc_bounds(week_start)
    prev_start = start - timedelta(days=7)

    reviews, correct = await _review_stats(db, user_id, start, end)
    prev_reviews, prev_correct = await _review_stats(db, user_id, prev_start, start)
    accuracy = round(correct / reviews * 100) if reviews else None
    prev_accuracy = round(prev_correct / prev_reviews * 100) if prev_reviews else None

    reach_dates = await progress.long_term_reach_dates(db, user_id)
    long_term_new = sum(1 for d in reach_dates if week_start <= d <= week_end)
    prev_long_term_new = sum(1 for d in reach_dates if prev_week_start <= d < week_start)

    routine_steps = await _routine_steps(db, user_id, start, end)
    prev_routine_steps = await _routine_steps(db, user_id, prev_start, start)

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "reviews": reviews,
        "reviews_delta": reviews - prev_reviews,
        "accuracy": accuracy,
        # 전주에 복습이 없으면 비교 대상이 없다 — 0% 에서 올랐다고 말하지 않는다
        "accuracy_delta": (
            None if accuracy is None or prev_accuracy is None else accuracy - prev_accuracy
        ),
        "long_term_new": long_term_new,
        "long_term_new_delta": long_term_new - prev_long_term_new,
        "routine_steps": routine_steps,
        "routine_steps_delta": routine_steps - prev_routine_steps,
        "listen": await _listen_delta(db, user_id, start, end),
        "streak_days": await _streak_days(db, user_id, settings, now),
        "has_data": reviews > 0,
    }
