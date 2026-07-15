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
