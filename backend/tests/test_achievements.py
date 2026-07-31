"""업적 배지 P3 — 기존 로그 실시간 집계 (적립 테이블 없음, 소급 반영)."""

from datetime import UTC, datetime, timedelta

from app.models import GameMatch, ReviewCard, ReviewLog, TypingRace
from app.models.friend import Friendship
from app.models.user import User
from tests.test_study import login, seed_items


async def _log_reviews(db, user_id: int, count: int, days_ago: int = 0) -> None:
    items = await seed_items(db, count=1)
    card = ReviewCard(
        user_id=user_id, item_id=items[0].id, state="review", due_at=datetime.now(UTC)
    )
    db.add(card)
    await db.flush()
    when = datetime.now(UTC) - timedelta(days=days_ago)
    for _ in range(count):
        db.add(
            ReviewLog(
                card_id=card.id,
                user_id=user_id,
                rating=3,
                correct=True,
                quiz_mode="choice_en2ko",
                state_before="review",
                reviewed_at=when,
            )
        )
    await db.flush()


async def test_achievements_all_locked_for_new_user(client, db_session):
    await login(client, db_session)
    res = await client.get("/api/study/achievements")
    assert res.status_code == 200
    body = res.json()
    assert body["achieved_count"] == 0
    assert body["total"] == len(body["items"]) > 0
    first = next(a for a in body["items"] if a["key"] == "first_review")
    assert first["achieved"] is False
    assert first["current"] == 0 and first["target"] == 1


async def test_first_review_and_word_progress(client, db_session):
    me = await login(client, db_session)
    await _log_reviews(db_session, me.id, count=3)
    await db_session.commit()

    res = await client.get("/api/study/achievements")
    items = {a["key"]: a for a in res.json()["items"]}
    assert items["first_review"]["achieved"] is True
    assert items["words_100"]["current"] == 1  # 단어 카드 1개
    assert items["words_100"]["achieved"] is False
    assert 0 < items["words_100"]["progress"] < 1


async def test_streak_7_achieved_with_consecutive_days(client, db_session):
    me = await login(client, db_session)
    for days_ago in range(7):
        await _log_reviews(db_session, me.id, count=1, days_ago=days_ago)
    await db_session.commit()

    res = await client.get("/api/study/achievements")
    items = {a["key"]: a for a in res.json()["items"]}
    assert items["streak_7"]["achieved"] is True
    assert items["streak_30"]["achieved"] is False
    assert items["streak_30"]["current"] == 7


async def test_first_win_from_any_game(client, db_session):
    me = await login(client, db_session)
    db_session.add(
        GameMatch(
            mode="pve",
            status="finished",
            player1_id=me.id,
            winner_id=me.id,
            p1_score=100,
            stats={},
        )
    )
    await db_session.commit()

    res = await client.get("/api/study/achievements")
    items = {a["key"]: a for a in res.json()["items"]}
    assert items["first_win"]["achieved"] is True
    assert items["games_10"]["current"] == 1
    # 첫 게임(참여) 단발 업적 — 테마 보상(레고) 매핑 대상
    assert items["first_game"]["achieved"] is True
    assert items["first_game"]["tier"] is None


async def test_typing_300_from_peak_cpm(client, db_session):
    me = await login(client, db_session)
    db_session.add(
        TypingRace(
            mode="solo",
            status="finished",
            player1_id=me.id,
            p1_chars=100,
            stats={"p1": {"peak_cpm": 320, "wpm": 64}},
        )
    )
    await db_session.commit()

    res = await client.get("/api/study/achievements")
    items = {a["key"]: a for a in res.json()["items"]}
    assert items["typing_300"]["achieved"] is True


async def test_tiered_achievements_progression(client, db_session):
    """티어 스티커 — 같은 지표의 초급/중급/고급/마스터 4단이 단계별로 열린다."""
    me = await login(client, db_session)
    await _log_reviews(db_session, me.id, count=120)
    await db_session.commit()

    res = await client.get("/api/study/achievements")
    items = {a["key"]: a for a in res.json()["items"]}

    # 복습 120회 → 초급(100) 달성, 중급(500) 진행 중
    assert items["reviews_100"]["achieved"] is True
    assert items["reviews_100"]["tier"] == "beginner"
    assert items["reviews_500"]["achieved"] is False
    assert items["reviews_500"]["current"] == 120
    assert items["reviews_5000"]["tier"] == "master"

    # 4단 티어 패밀리 존재 — 스트릭·승리·게임·타자·단어
    assert items["streak_365"]["target"] == 365
    assert items["wins_300"]["tier"] == "master"
    assert items["games_500"]["tier"] == "master"
    assert items["typing_600"]["tier"] == "master"
    assert items["words_1000"]["tier"] == "master"

    # 패밀리 그룹 필드 — 프론트 섹션 렌더용
    assert items["wins_10"]["family"] == "game"
    assert items["streak_7"]["family"] == "streak"
    assert items["first_friend"]["family"] == "social"
    # 단발 업적은 tier 없음
    assert items["first_review"]["tier"] is None

    # 오늘의 목표(가볍게 10/기본 20/열심히 50) — 하루 최대 복습 수가 지표.
    # 위에서 하루에 120개 복습 → 셋 다 달성
    assert items["goal_light"]["achieved"] is True
    assert items["goal_basic"]["achieved"] is True
    assert items["goal_hard"]["achieved"] is True
    assert items["goal_hard"]["target"] == 50


async def test_daily_goal_uses_single_day_peak(client, db_session):
    """이틀에 나눠 15개씩 — 누적 30이어도 하루 최대 15라 기본(20) 미달성."""
    me = await login(client, db_session)
    await _log_reviews(db_session, me.id, count=15, days_ago=0)
    await _log_reviews(db_session, me.id, count=15, days_ago=1)
    await db_session.commit()

    res = await client.get("/api/study/achievements")
    items = {a["key"]: a for a in res.json()["items"]}
    assert items["goal_light"]["achieved"] is True  # 하루 15 >= 10
    assert items["goal_basic"]["achieved"] is False  # 하루 최대 15 < 20
    assert items["goal_basic"]["current"] == 15


async def test_achievements_expose_reward_theme(client, db_session):
    """업적 스티커에 보상 테마 예고 — 규칙 있는 업적만 reward_theme."""
    from app.models import ThemeRewardRule

    db_session.add(ThemeRewardRule(achievement_key="first_friend", theme_key="candy"))
    await db_session.commit()
    await login(client, db_session)

    res = await client.get("/api/study/achievements")
    items = {a["key"]: a for a in res.json()["items"]}
    assert items["first_friend"]["reward_theme"] == "candy"
    assert items["first_review"]["reward_theme"] is None


async def _seed_exam(db, question_count=20):
    from app.models import Content, Exam

    content = Content(source="manual", title="업적 시험", status="ready")
    db.add(content)
    await db.flush()
    exam = Exam(content_id=content.id, round=1, question_count=question_count)
    db.add(exam)
    await db.flush()
    return exam


async def _submit_exam(db, exam, user_id, score, duration_ms=1000, submitted=True):
    from app.models import ExamAttempt

    db.add(
        ExamAttempt(
            exam_id=exam.id,
            user_id=user_id,
            submitted_at=datetime.now(UTC) if submitted else None,
            score=score if submitted else None,
            correct_count=(score // 5) if submitted else None,
            duration_ms=duration_ms if submitted else None,
            answers=[0] * exam.question_count if submitted else None,
        )
    )
    await db.flush()


async def test_exam_family_submit_counts(client, db_session):
    """AC-5: 제출 수 지표 — first_exam 단발 + exams_10/30/100 티어 (family exam)."""
    me = await login(client, db_session)
    exam = await _seed_exam(db_session)
    for _ in range(3):
        await _submit_exam(db_session, exam, me.id, score=55)
    # 미제출(진행 중/이탈) attempt 는 집계 제외
    await _submit_exam(db_session, exam, me.id, score=0, submitted=False)
    await db_session.commit()

    res = await client.get("/api/study/achievements")
    items = {a["key"]: a for a in res.json()["items"]}
    assert items["first_exam"]["achieved"] is True
    assert items["first_exam"]["tier"] is None
    assert items["exams_10"]["current"] == 3 and items["exams_10"]["achieved"] is False
    assert items["exams_10"]["tier"] == "beginner"
    assert items["exams_30"]["tier"] == "intermediate"
    assert items["exams_100"]["tier"] == "advanced"
    for key in ("first_exam", "exam_perfect", "exam_champion", "exams_10"):
        assert items[key]["family"] == "exam"


async def test_exam_perfect_requires_100(client, db_session):
    """AC-5: 만점 업적 — 100점 응시가 존재해야 달성 (95점은 미달)."""
    me = await login(client, db_session)
    exam = await _seed_exam(db_session)
    await _submit_exam(db_session, exam, me.id, score=95)
    await db_session.commit()

    items = {a["key"]: a for a in (await client.get("/api/study/achievements")).json()["items"]}
    assert items["exam_perfect"]["achieved"] is False

    await _submit_exam(db_session, exam, me.id, score=100)
    await db_session.commit()
    items = {a["key"]: a for a in (await client.get("/api/study/achievements")).json()["items"]}
    assert items["exam_perfect"]["achieved"] is True


async def test_exam_champion_tie_on_best_score(client, db_session):
    """AC-5: 1위 등극 — 공동 1위 = best score 동률 기준 (duration 무관)."""
    from tests.test_friends import make_user

    me = await login(client, db_session)
    rival = await make_user(db_session, "rival@example.com", "라이벌")

    # 시험 1: 라이벌이 단독 1위 (95 > 90) — 나는 champion 아님
    exam1 = await _seed_exam(db_session)
    await _submit_exam(db_session, exam1, me.id, score=90, duration_ms=1000)
    await _submit_exam(db_session, exam1, rival.id, score=95, duration_ms=9000)
    await db_session.commit()
    items = {a["key"]: a for a in (await client.get("/api/study/achievements")).json()["items"]}
    assert items["exam_champion"]["achieved"] is False

    # 시험 2: 동점 100 — duration 이 느려도 공동 1위로 인정
    exam2 = await _seed_exam(db_session)
    await _submit_exam(db_session, exam2, rival.id, score=100, duration_ms=100)
    await _submit_exam(db_session, exam2, me.id, score=100, duration_ms=99999)
    await db_session.commit()
    items = {a["key"]: a for a in (await client.get("/api/study/achievements")).json()["items"]}
    assert items["exam_champion"]["achieved"] is True


async def test_first_friend_requires_accepted(client, db_session):
    me = await login(client, db_session)
    other = User(google_sub="g-ach", email="ach@example.com", name="친구")
    db_session.add(other)
    await db_session.flush()
    db_session.add(Friendship(requester_id=other.id, addressee_id=me.id, status="pending"))
    await db_session.commit()

    res = await client.get("/api/study/achievements")
    items = {a["key"]: a for a in res.json()["items"]}
    assert items["first_friend"]["achieved"] is False

    fr = (
        await db_session.execute(
            Friendship.__table__.select().where(Friendship.requester_id == other.id)
        )
    ).first()
    await db_session.execute(
        Friendship.__table__.update().where(Friendship.id == fr.id).values(status="accepted")
    )
    await db_session.commit()

    res = await client.get("/api/study/achievements")
    items = {a["key"]: a for a in res.json()["items"]}
    assert items["first_friend"]["achieved"] is True
