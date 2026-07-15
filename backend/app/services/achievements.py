"""업적 배지 — 기존 로그 실시간 집계 (P3 리텐션).

XP 와 같은 원칙: 별도 적립 테이블 없이 원본 기록에서 매번 계산한다.
과거 기록이 전부 소급 반영되고, 저장 로직 버그로 업적이 어긋날 일이 없다.
"""

from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    GameMatch,
    LearningItem,
    QuizRoyaleMatch,
    QuizRoyalePlayer,
    ReviewCard,
    ReviewLog,
    ScrambleRace,
    TypingRace,
)
from app.models.friend import Friendship

KST = timezone(timedelta(hours=9))
STREAK_WINDOW_DAYS = 90

# (key, title, desc, target) — 진행률 표시용. 판정은 current >= target
DEFINITIONS = (
    ("first_review", "첫 걸음", "첫 복습을 완료했어요", 1),
    ("words_100", "첫 100단어", "단어 100개 학습을 시작했어요", 100),
    ("reviews_1000", "복습 마스터", "누적 복습 1,000회를 달성했어요", 1000),
    ("streak_7", "일주일 개근", "7일 연속으로 학습했어요", 7),
    ("streak_30", "한 달 개근", "30일 연속으로 학습했어요", 30),
    ("first_win", "첫 승리", "게임에서 처음 이겼어요", 1),
    ("games_10", "게임 단골", "게임 10판에 참여했어요", 10),
    ("typing_300", "타자 신동", "타자 최고 300타를 넘겼어요", 300),
    ("first_friend", "첫 친구", "첫 친구와 연결됐어요", 1),
)


def current_streak(daily: dict[str, int], today) -> int:
    """오늘(아직 안 했으면 어제)부터 거꾸로 연속 학습일 계산 — stats 와 동일 규칙."""
    streak = 0
    cursor = today
    if daily.get(cursor.isoformat(), 0) == 0:
        cursor -= timedelta(days=1)
    while daily.get(cursor.isoformat(), 0) > 0:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


async def _count(db: AsyncSession, stmt) -> int:
    return (await db.execute(stmt)).scalar_one()


async def compute(db: AsyncSession, user_id: int) -> list[dict]:
    now = datetime.now(UTC)

    total_reviews = await _count(
        db, select(func.count(ReviewLog.id)).where(ReviewLog.user_id == user_id)
    )
    word_cards = await _count(
        db,
        select(func.count(ReviewCard.id))
        .join(LearningItem, LearningItem.id == ReviewCard.item_id)
        .where(ReviewCard.user_id == user_id, LearningItem.item_type == "word"),
    )

    recent = (
        await db.execute(
            select(ReviewLog.reviewed_at).where(
                ReviewLog.user_id == user_id,
                ReviewLog.reviewed_at >= now - timedelta(days=STREAK_WINDOW_DAYS),
            )
        )
    ).scalars()
    daily: dict[str, int] = {}
    for reviewed_at in recent:
        key = reviewed_at.astimezone(KST).date().isoformat()
        daily[key] = daily.get(key, 0) + 1
    streak = current_streak(daily, now.astimezone(KST).date())

    tetris_played = await _count(
        db,
        select(func.count(GameMatch.id)).where(
            or_(GameMatch.player1_id == user_id, GameMatch.player2_id == user_id),
            GameMatch.status == "finished",
        ),
    )
    tetris_wins = await _count(
        db,
        select(func.count(GameMatch.id)).where(
            GameMatch.winner_id == user_id, GameMatch.status == "finished"
        ),
    )
    typing_rows = (
        (
            await db.execute(
                select(TypingRace).where(
                    or_(TypingRace.player1_id == user_id, TypingRace.player2_id == user_id),
                    TypingRace.status == "finished",
                )
            )
        )
        .scalars()
        .all()
    )
    typing_wins = sum(1 for r in typing_rows if r.winner_id == user_id)
    peak_cpm = 0
    for row in typing_rows:
        slot = "p1" if row.player1_id == user_id else "p2"
        stats = (row.stats or {}).get(slot) or {}
        peak_cpm = max(peak_cpm, int(stats.get("peak_cpm") or 0))

    quiz_rows = (
        await db.execute(
            select(func.count(QuizRoyalePlayer.id), func.count().filter(QuizRoyalePlayer.rank == 1))
            .join(QuizRoyaleMatch, QuizRoyaleMatch.id == QuizRoyalePlayer.match_id)
            .where(
                QuizRoyalePlayer.user_id == user_id,
                QuizRoyaleMatch.status == "finished",
            )
        )
    ).one()
    quiz_played, quiz_wins = int(quiz_rows[0]), int(quiz_rows[1])

    scramble_rows = (
        await db.execute(
            select(
                func.count(ScrambleRace.id),
                func.count().filter(ScrambleRace.winner_id == user_id),
            ).where(
                or_(ScrambleRace.player1_id == user_id, ScrambleRace.player2_id == user_id),
                ScrambleRace.status == "finished",
            )
        )
    ).one()
    scramble_played, scramble_wins = int(scramble_rows[0]), int(scramble_rows[1])

    friends = await _count(
        db,
        select(func.count(Friendship.id)).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        ),
    )

    currents = {
        "first_review": total_reviews,
        "words_100": word_cards,
        "reviews_1000": total_reviews,
        "streak_7": streak,
        "streak_30": streak,
        "first_win": tetris_wins + typing_wins + quiz_wins + scramble_wins,
        "games_10": tetris_played + len(typing_rows) + quiz_played + scramble_played,
        "typing_300": peak_cpm,
        "first_friend": friends,
    }

    items = []
    for key, title, desc, target in DEFINITIONS:
        current = currents[key]
        items.append(
            {
                "key": key,
                "title": title,
                "desc": desc,
                "current": min(current, target),
                "target": target,
                "achieved": current >= target,
                "progress": min(1.0, current / target),
            }
        )
    return items
