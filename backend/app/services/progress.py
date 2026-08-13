"""학습 진행 지표 — 오답 정리(weak) 선정 + 장기 기억(long-term) 산출.

기획: docs/proposal/duolingo-benchmark-2026-08.md / 스펙: docs/specs/learning.md
api/study.py 에서 분리 (2026-08-05 유지보수 리팩토링) — 선정·산출 규칙의 정본.
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearningItem, ReviewCard, ReviewLog, XpSpend
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


async def long_term_reach_dates(db: AsyncSession, user_id: int) -> list[date]:
    """카드별 "간격 7일+ 첫 도달" 날짜(KST) — 현재 가시성과 무관한 역사적 도달 기록.

    장기 기억 추이(long_term_stats)와 주간 성적표(services/weekly_report)의 공용 재료.
    """
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
    return [r.astimezone(KST).date() for r in reach_rows]


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

    reach_dates = await long_term_reach_dates(db, user_id)

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


# ---------- XP (적립 실시간 집계 + 소비 원장) ----------


async def total_xp(db: AsyncSession, user_id: int) -> int:
    """누적 XP — 복습 10 + 게임 참여 20 + 테트리스 승리 30 + 시험 20+점수/10
    + 미션 보너스. 적립 테이블 없이 로그 실시간 집계 (소급 반영 원칙).
    api/study.py stats 에서 이관 (2026-08-05 — XP 상점이 재사용).
    """
    from sqlalchemy import or_

    from app.models import (
        BingoMatch,
        DictationRace,
        ExamAttempt,
        GameMatch,
        QuizRoyaleMatch,
        QuizRoyalePlayer,
        ScrambleRace,
        TypingRace,
    )
    from app.services import retention

    total_reviews = (
        await db.execute(select(func.count(ReviewLog.id)).where(ReviewLog.user_id == user_id))
    ).scalar_one()
    tetris_played = (
        await db.execute(
            select(func.count(GameMatch.id)).where(
                or_(GameMatch.player1_id == user_id, GameMatch.player2_id == user_id),
                GameMatch.status == "finished",
            )
        )
    ).scalar_one()
    tetris_wins = (
        await db.execute(
            select(func.count(GameMatch.id)).where(
                GameMatch.winner_id == user_id, GameMatch.status == "finished"
            )
        )
    ).scalar_one()
    typing_played = (
        await db.execute(
            select(func.count(TypingRace.id)).where(
                or_(TypingRace.player1_id == user_id, TypingRace.player2_id == user_id),
                TypingRace.status == "finished",
            )
        )
    ).scalar_one()
    quiz_played = (
        await db.execute(
            select(func.count(QuizRoyalePlayer.id))
            .join(QuizRoyaleMatch, QuizRoyaleMatch.id == QuizRoyalePlayer.match_id)
            .where(
                QuizRoyalePlayer.user_id == user_id,
                QuizRoyaleMatch.status == "finished",
            )
        )
    ).scalar_one()
    scramble_played = (
        await db.execute(
            select(func.count(ScrambleRace.id)).where(
                or_(ScrambleRace.player1_id == user_id, ScrambleRace.player2_id == user_id),
                ScrambleRace.status == "finished",
            )
        )
    ).scalar_one()
    dictation_played = (
        await db.execute(
            select(func.count(DictationRace.id)).where(
                or_(DictationRace.player1_id == user_id, DictationRace.player2_id == user_id),
                DictationRace.status == "finished",
            )
        )
    ).scalar_one()
    # 빙고(2026-08-10 출시) — 참여만 20 XP, 승리 보너스 없음(30은 테트리스 전용 산식)
    bingo_played = (
        await db.execute(
            select(func.count(BingoMatch.id)).where(
                or_(BingoMatch.player1_id == user_id, BingoMatch.player2_id == user_id),
                BingoMatch.status == "finished",
            )
        )
    ).scalar_one()
    # 시험 XP — 제출 20 + 점수 10점당 1 (api/exams.py exam_xp 와 동일 산식).
    # 건별 floor(score/10) 합 — 합계에 //10 하면 건별 산식과 어긋난다 (25+15: 3 vs 4)
    exam_submits, exam_score_bonus = (
        await db.execute(
            select(
                func.count(ExamAttempt.id),
                func.coalesce(func.sum(func.floor(ExamAttempt.score / 10.0)), 0),
            ).where(ExamAttempt.user_id == user_id, ExamAttempt.submitted_at.is_not(None))
        )
    ).one()

    return (
        total_reviews * 10
        + (
            tetris_played
            + typing_played
            + quiz_played
            + scramble_played
            + dictation_played
            + bingo_played
        )
        * 20
        + tetris_wins * 30
        + int(exam_submits) * 20
        + int(exam_score_bonus)
        + await retention.quest_bonus_xp(db, user_id)
        + await routine_xp(db, user_id)
    )


async def routine_xp(db: AsyncSession, user_id: int) -> int:
    """루틴 XP — 완주 콘텐츠(6단계) x 50 + 요약 제출 x 20 (ted-routine P1).

    원장 행에서 실시간 파생 — 적립 테이블 없음 원칙 유지.
    """
    from app.models import ContentRoutineProgress, ContentSummary
    from app.models.routine import ROUTINE_STEP_COUNT

    completed = (
        await db.execute(
            select(func.count()).select_from(
                select(ContentRoutineProgress.content_id)
                .where(ContentRoutineProgress.user_id == user_id)
                .group_by(ContentRoutineProgress.content_id)
                .having(func.count(ContentRoutineProgress.id) >= ROUTINE_STEP_COUNT)
                .subquery()
            )
        )
    ).scalar_one()
    # distinct content_id — 같은 콘텐츠 재제출은 이력으로 쌓이지만 XP 는 1회만
    # 인정 (2026-08-11 무한 파밍 픽스 전: COUNT(id) 라 재제출마다 20 XP 지급됨)
    summaries = (
        await db.execute(
            select(func.count(func.distinct(ContentSummary.content_id))).where(
                ContentSummary.user_id == user_id
            )
        )
    ).scalar_one()
    return completed * 50 + summaries * 20


async def spent_xp(db: AsyncSession, user_id: int) -> int:
    """소비 XP 합 — xp_spends 원장 (테마 구매 등)."""
    return (
        await db.execute(
            select(func.coalesce(func.sum(XpSpend.amount), 0)).where(XpSpend.user_id == user_id)
        )
    ).scalar_one()


async def available_xp(db: AsyncSession, user_id: int) -> int:
    """가용 XP = 누적 - 소비. 레벨은 누적 XP 기준 불변 — 구매해도 레벨은 안 내려간다."""
    return await total_xp(db, user_id) - await spent_xp(db, user_id)


async def revert_if_overdrawn(
    db: AsyncSession,
    user_id: int,
    rows: list,
    extra_revert: Callable[[], None] | None = None,
) -> bool:
    """구매 커밋 직후 재검증 — 동시 구매 경합(TOCTOU)으로 가용 XP 가 음수가 되면
    방금 커밋한 행을 삭제하고(+extra_revert 로 부가 상태 되돌림) True 를 반환한다.

    사전 잔액 검증(available_xp < price)과 커밋 사이에 다른 구매가 끼면 둘 다
    통과해 이중 차감될 수 있다. FOR UPDATE 잠금은 asyncpg(운영)에는 유효하지만
    테스트가 쓰는 aiosqlite 에선 no-op 이라 검증이 안 된다 — 대신 커밋 후
    재확인 + 보상 삭제로 두 백엔드에서 동일하게 동작·검증 가능한 방식을 쓴다
    (2026-08-11 TOCTOU 픽스). 호출자는 True 반환 시 422 insufficient_xp 로 응답한다.
    """
    if await available_xp(db, user_id) >= 0:
        return False
    if extra_revert is not None:
        extra_revert()
    for row in rows:
        await db.delete(row)
    await db.commit()
    return True
