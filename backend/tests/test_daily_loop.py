"""데일리 루프 P1 — 주간 학습 리더보드(친구 중심) + 게임 최고 기록."""

from datetime import UTC, datetime, timedelta

from app.models import (
    GameMatch,
    QuizRoyaleMatch,
    ReviewLog,
    TypingRace,
    User,
)
from app.models.friend import Friendship
from tests.test_study import login, seed_items


async def _log_reviews(db, user_id, count, days_ago=0):
    from app.models import LearningItem, ReviewCard

    item = LearningItem(
        item_type="word",
        en_text=f"lbword{user_id}-{days_ago}",
        ko_text="뜻",
        normalized_key=f"lbword{user_id}-{days_ago}",
        review_status="approved",
    )
    db.add(item)
    await db.flush()
    card = ReviewCard(user_id=user_id, item_id=item.id, state="review", due_at=datetime.now(UTC))
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


async def test_study_leaderboard_ranks_me_and_friends(client, db_session):
    """주간(7일) 복습 수로 나+수락된 친구만 랭킹 — 남남은 제외."""
    me = await login(client, db_session)
    friend = User(google_sub="g-lb1", email="lb1@example.com", name="친구")
    stranger = User(google_sub="g-lb2", email="lb2@example.com", name="남남")
    db_session.add_all([friend, stranger])
    await db_session.flush()
    db_session.add(Friendship(requester_id=me.id, addressee_id=friend.id, status="accepted"))
    await _log_reviews(db_session, me.id, 5)
    await _log_reviews(db_session, friend.id, 9)
    await _log_reviews(db_session, stranger.id, 99)
    await _log_reviews(db_session, me.id, 7, days_ago=10)  # 7일 밖 — 제외
    await db_session.commit()

    res = await client.get("/api/study/leaderboard")
    assert res.status_code == 200
    rows = res.json()["items"]
    assert [(r["name"], r["reviews"], r["me"]) for r in rows] == [
        ("친구", 9, False),
        (me.name, 5, True),
    ]
    assert rows[0]["rank"] == 1 and rows[1]["rank"] == 2


async def test_game_bests_across_three_games(client, db_session):
    """게임별 내 최고 기록 — 테트리스 점수 / 퀴즈 점수 / 타자 최고 타."""
    me = await login(client, db_session)
    await seed_items(db_session, count=1)

    db_session.add_all(
        [
            GameMatch(
                mode="pve",
                status="finished",
                player1_id=me.id,
                p1_score=459,
                p2_score=631,
                stats={},
            ),
            QuizRoyaleMatch(
                host_id=me.id,
                mode="solo",
                status="finished",
                players={
                    "players": [
                        {"user_id": me.id, "name": me.name, "score": 470, "rank": 1},
                        {"user_id": None, "name": "봇", "score": 300, "rank": 2},
                    ]
                },
            ),
            TypingRace(
                mode="solo",
                status="finished",
                player1_id=me.id,
                p1_chars=250,
                stats={
                    "p1": {
                        "name": me.name,
                        "wpm": 41.0,
                        "cpm": 205,
                        "peak_cpm": 280,
                        "accuracy": 0.95,
                        "sentences": 8,
                        "chars": 250,
                    }
                },
            ),
        ]
    )
    await db_session.commit()

    res = await client.get("/api/game/bests")
    assert res.status_code == 200
    body = res.json()
    assert body["tetris_best_score"] == 459
    assert body["quiz_best_score"] == 470
    assert body["typing_best_cpm"] == 280


async def test_game_bests_empty_for_new_user(client, db_session):
    await login(client, db_session)
    res = await client.get("/api/game/bests")
    body = res.json()
    assert body == {
        "tetris_best_score": 0,
        "quiz_best_score": 0,
        "typing_best_cpm": 0,
    }


async def test_stats_include_xp_and_level(client, db_session):
    """XP = 복습x10 + 게임 참여x20 + 승리 보너스x30, 레벨 = 500XP 단위."""
    me = await login(client, db_session, email="xp@example.com")
    await _log_reviews(db_session, me.id, 12)
    db_session.add(
        GameMatch(
            mode="pve",
            status="finished",
            player1_id=me.id,
            winner_id=me.id,
            p1_score=100,
            p2_score=50,
            stats={},
        )
    )
    await db_session.commit()

    res = await client.get("/api/study/stats")
    body = res.json()
    # 복습 120 + 참여 20 + 승리 30 = 170
    assert body["xp"] == 170
    assert body["level"] == 1
    assert 0 <= body["level_progress"] < 1
