"""업적 배지 — 기존 로그 실시간 집계 (P3 리텐션).

XP 와 같은 원칙: 별도 적립 테이블 없이 원본 기록에서 매번 계산한다.
과거 기록이 전부 소급 반영되고, 저장 로직 버그로 업적이 어긋날 일이 없다.
"""

from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BingoMatch,
    DictationRace,
    Exam,
    ExamAttempt,
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
from app.services.exams import POINTS_PER_QUESTION

KST = timezone(timedelta(hours=9))
STREAK_WINDOW_DAYS = 90

# (key, title, desc, target, tier, family, metric)
# tier: None(단발) | beginner(초급) | intermediate(중급) | advanced(고급) | master(마스터)
# family: 프론트 섹션 그룹 (study/streak/game/social). metric: currents 조회 키.
# 판정은 current >= target — 같은 지표의 티어들이 단계별로 열린다.
DEFINITIONS = (
    # 학습 — 복습·단어
    ("first_review", "첫 걸음", "첫 복습을 완료했어요", 1, None, "study", "reviews"),
    (
        "reviews_100",
        "복습 입문",
        "누적 복습 100회를 달성했어요",
        100,
        "beginner",
        "study",
        "reviews",
    ),
    (
        "reviews_500",
        "복습 중수",
        "누적 복습 500회를 달성했어요",
        500,
        "intermediate",
        "study",
        "reviews",
    ),
    (
        "reviews_1000",
        "복습 고수",
        "누적 복습 1,000회를 달성했어요",
        1000,
        "advanced",
        "study",
        "reviews",
    ),
    (
        "reviews_5000",
        "복습 마스터",
        "누적 복습 5,000회를 달성했어요",
        5000,
        "master",
        "study",
        "reviews",
    ),
    ("words_100", "단어 입문", "단어 100개 학습을 시작했어요", 100, "beginner", "study", "words"),
    (
        "words_300",
        "단어 중수",
        "단어 300개 학습을 시작했어요",
        300,
        "intermediate",
        "study",
        "words",
    ),
    ("words_600", "단어 고수", "단어 600개 학습을 시작했어요", 600, "advanced", "study", "words"),
    (
        "words_1000",
        "단어 마스터",
        "단어 1,000개 학습을 시작했어요",
        1000,
        "master",
        "study",
        "words",
    ),
    # 하루 최대 복습 수 티어 — 구 프리셋(10/20/50) 기준 유지. 2026-08-05 프리셋
    # 상향(15/30/50)과 분리 — 타깃을 올리면 이미 달성한 스티커가 소급 롤백된다
    (
        "goal_light",
        "가볍게 목표",
        "하루 10개 복습을 달성했어요",
        10,
        "beginner",
        "study",
        "peak_daily",
    ),
    (
        "goal_basic",
        "기본 목표",
        "하루 20개 복습을 달성했어요",
        20,
        "intermediate",
        "study",
        "peak_daily",
    ),
    (
        "goal_hard",
        "열심히 목표",
        "하루 50개 복습을 달성했어요",
        50,
        "advanced",
        "study",
        "peak_daily",
    ),
    # 꾸준함 — 연속 학습
    ("streak_7", "일주일 개근", "7일 연속으로 학습했어요", 7, "beginner", "streak", "streak"),
    ("streak_30", "한 달 개근", "30일 연속으로 학습했어요", 30, "intermediate", "streak", "streak"),
    ("streak_100", "백일 개근", "100일 연속으로 학습했어요", 100, "advanced", "streak", "streak"),
    ("streak_365", "일 년 개근", "365일 연속으로 학습했어요", 365, "master", "streak", "streak"),
    # 게임 — 승리·참여·타자
    ("first_game", "첫 게임", "게임에 처음 참여했어요", 1, None, "game", "games"),
    ("first_win", "첫 승리", "게임에서 처음 이겼어요", 1, None, "game", "wins"),
    ("wins_10", "승리 입문", "게임에서 10번 이겼어요", 10, "beginner", "game", "wins"),
    ("wins_30", "승리 중수", "게임에서 30번 이겼어요", 30, "intermediate", "game", "wins"),
    ("wins_100", "승리 고수", "게임에서 100번 이겼어요", 100, "advanced", "game", "wins"),
    ("wins_300", "승리 마스터", "게임에서 300번 이겼어요", 300, "master", "game", "wins"),
    ("games_10", "게임 단골", "게임 10판에 참여했어요", 10, "beginner", "game", "games"),
    ("games_50", "게임 애호가", "게임 50판에 참여했어요", 50, "intermediate", "game", "games"),
    ("games_200", "게임 고수", "게임 200판에 참여했어요", 200, "advanced", "game", "games"),
    ("games_500", "게임 마스터", "게임 500판에 참여했어요", 500, "master", "game", "games"),
    ("typing_300", "타자 신동", "타자 최고 300타를 넘겼어요", 300, "beginner", "game", "typing"),
    (
        "typing_400",
        "타자 중수",
        "타자 최고 400타를 넘겼어요",
        400,
        "intermediate",
        "game",
        "typing",
    ),
    ("typing_500", "타자 고수", "타자 최고 500타를 넘겼어요", 500, "advanced", "game", "typing"),
    ("typing_600", "타자 마스터", "타자 최고 600타를 넘겼어요", 600, "master", "game", "typing"),
    # 소셜 — 친구
    ("first_friend", "첫 친구", "첫 친구와 연결됐어요", 1, None, "social", "friends"),
    ("friends_5", "우정 입문", "친구 5명과 연결됐어요", 5, "beginner", "social", "friends"),
    ("friends_10", "마당발", "친구 10명과 연결됐어요", 10, "intermediate", "social", "friends"),
    # 시험 — 제출·만점·1위 (docs/specs/library-exam.md)
    ("first_exam", "첫 시험", "첫 시험을 제출했어요", 1, None, "exam", "exam_submits"),
    ("exam_perfect", "만점", "시험에서 만점을 받았어요", 1, None, "exam", "exam_perfect"),
    # 공동 1위 = best score 동률 기준 (duration 무관 — 최고 점수 도달 성취 인정)
    ("exam_champion", "1위 등극", "시험 랭킹 1위에 올랐어요", 1, None, "exam", "exam_champion"),
    ("exams_10", "응시 입문", "시험 10회를 제출했어요", 10, "beginner", "exam", "exam_submits"),
    (
        "exams_30",
        "응시 중수",
        "시험 30회를 제출했어요",
        30,
        "intermediate",
        "exam",
        "exam_submits",
    ),
    (
        "exams_100",
        "응시 고수",
        "시험 100회를 제출했어요",
        100,
        "advanced",
        "exam",
        "exam_submits",
    ),
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

    dictation_rows = (
        await db.execute(
            select(
                func.count(DictationRace.id),
                func.count().filter(DictationRace.winner_id == user_id),
            ).where(
                or_(DictationRace.player1_id == user_id, DictationRace.player2_id == user_id),
                DictationRace.status == "finished",
            )
        )
    ).one()
    dictation_played, dictation_wins = int(dictation_rows[0]), int(dictation_rows[1])

    # 빙고(2026-08-10 출시) — games_played 류 제네릭 카운터에만 포함, 승리 지표는
    # XP 산식과 동일하게 대상 외(승리 보너스 없음 — 게임별 전용 업적도 아직 없음)
    bingo_played = await _count(
        db,
        select(func.count(BingoMatch.id)).where(
            or_(BingoMatch.player1_id == user_id, BingoMatch.player2_id == user_id),
            BingoMatch.status == "finished",
        ),
    )

    friends = await _count(
        db,
        select(func.count(Friendship.id)).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        ),
    )

    # 시험 — 제출 완료 attempt 만 집계 (진행 중/이탈은 무영향)
    exam_submits = await _count(
        db,
        select(func.count(ExamAttempt.id)).where(
            ExamAttempt.user_id == user_id, ExamAttempt.submitted_at.is_not(None)
        ),
    )
    # 만점 = question_count x POINTS_PER_QUESTION — 100 하드코딩은 문항 5~19개(5점/문항)
    # 콘텐츠에서 전 문항 정답이어도 100점 미만이라 업적을 놓쳤다 (L2 픽스)
    exam_perfect = await _count(
        db,
        select(func.count(ExamAttempt.id))
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .where(
            ExamAttempt.user_id == user_id,
            ExamAttempt.score == Exam.question_count * POINTS_PER_QUESTION,
        ),
    )
    # 현 1위 시험 수 — 공동 1위 = best score 동률 기준 (duration 무관, spec §4).
    # 순위를 뺏기면 스티커는 꺼질 수 있으나 테마 보상 grant 는 영구 (기존 원칙)
    my_best = (
        select(ExamAttempt.exam_id, func.max(ExamAttempt.score).label("mine"))
        .where(ExamAttempt.user_id == user_id, ExamAttempt.submitted_at.is_not(None))
        .group_by(ExamAttempt.exam_id)
        .subquery()
    )
    overall_best = (
        select(ExamAttempt.exam_id, func.max(ExamAttempt.score).label("best"))
        .where(ExamAttempt.submitted_at.is_not(None))
        .group_by(ExamAttempt.exam_id)
        .subquery()
    )
    exam_champion = await _count(
        db,
        select(func.count())
        .select_from(my_best.join(overall_best, my_best.c.exam_id == overall_best.c.exam_id))
        .where(my_best.c.mine == overall_best.c.best),
    )

    # 지표 하나가 티어 여러 개를 먹인다 — 정의는 metric 키로 조회
    currents = {
        "reviews": total_reviews,
        "words": word_cards,
        "streak": streak,
        # 하루 최대 복습 수 — 오늘의 목표 티어(가볍게/기본/열심히) 판정.
        # streak 와 같은 90일 창(daily) 재사용 — 그 이전의 피크는 반영되지 않는다
        "peak_daily": max(daily.values(), default=0),
        "wins": tetris_wins + typing_wins + quiz_wins + scramble_wins + dictation_wins,
        "games": tetris_played
        + len(typing_rows)
        + quiz_played
        + scramble_played
        + dictation_played
        + bingo_played,
        "typing": peak_cpm,
        "friends": friends,
        "exam_submits": exam_submits,
        "exam_perfect": exam_perfect,
        "exam_champion": exam_champion,
    }

    items = []
    for key, title, desc, target, tier, family, metric in DEFINITIONS:
        current = currents[metric]
        items.append(
            {
                "key": key,
                "title": title,
                "desc": desc,
                "current": min(current, target),
                "target": target,
                "achieved": current >= target,
                "progress": min(1.0, current / target),
                "tier": tier,
                "family": family,
            }
        )
    return items
