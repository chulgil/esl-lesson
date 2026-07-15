"""게임별 주간 리더보드 P3 — 최근 7일 최고 기록 top5 (게임 허브 표시용)."""

from datetime import UTC, datetime, timedelta

from app.models import GameMatch, QuizRoyaleMatch, QuizRoyalePlayer, TypingRace, User
from tests.test_study import login

NOW = datetime.now(UTC)


async def test_leaderboards_rank_per_game_and_mark_me(client, db_session):
    me = await login(client, db_session)
    rival = User(google_sub="g-lbx", email="lbx@example.com", name="라이벌", nickname="라이벌")
    db_session.add(rival)
    await db_session.flush()

    db_session.add_all(
        [
            # 테트리스: 나 300(p1) vs 라이벌 500(p2) — 최고 점수 순
            GameMatch(
                mode="pvp",
                status="finished",
                player1_id=me.id,
                player2_id=rival.id,
                p1_score=300,
                p2_score=500,
                stats={},
                ended_at=NOW - timedelta(days=1),
            ),
            # 8일 전 999점 — 주간 창 밖, 제외
            GameMatch(
                mode="pve",
                status="finished",
                player1_id=me.id,
                p1_score=999,
                stats={},
                ended_at=NOW - timedelta(days=8),
            ),
            # 퀴즈: 나 470 — 집계는 정규 참가 기록(봇은 저장 시 제외)
            QuizRoyaleMatch(
                id=902,
                host_id=me.id,
                mode="solo",
                status="finished",
                players={
                    "players": [
                        {"user_id": me.id, "name": me.name, "score": 470, "rank": 1},
                        {"user_id": None, "name": "봇", "score": 999, "rank": 2},
                    ]
                },
                ended_at=NOW - timedelta(hours=2),
            ),
            QuizRoyalePlayer(match_id=902, user_id=me.id, score=470, rank=1),
            # 타자: 나 280 vs 라이벌 310
            TypingRace(
                mode="race",
                status="finished",
                player1_id=me.id,
                player2_id=rival.id,
                stats={
                    "p1": {"peak_cpm": 280},
                    "p2": {"peak_cpm": 310},
                },
                ended_at=NOW - timedelta(hours=3),
            ),
        ]
    )
    await db_session.commit()

    res = await client.get("/api/game/leaderboards")
    assert res.status_code == 200
    body = res.json()

    assert [(r["name"], r["value"], r["me"]) for r in body["tetris"]] == [
        ("라이벌", 500, False),
        (me.nickname, 300, True),
    ]
    assert [(r["name"], r["value"], r["me"]) for r in body["quiz"]] == [
        (me.nickname, 470, True),
    ]
    assert [(r["name"], r["value"], r["me"]) for r in body["typing"]] == [
        ("라이벌", 310, False),
        (me.nickname, 280, True),
    ]


async def test_leaderboards_empty_and_requires_auth(client, db_session):
    res = await client.get("/api/game/leaderboards")
    assert res.status_code == 401

    await login(client, db_session)
    res = await client.get("/api/game/leaderboards")
    assert res.json() == {"tetris": [], "quiz": [], "typing": [], "scramble": [], "dictation": []}
