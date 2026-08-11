"""플레이어 배지·타자 개선 — 마스코트/칭호, 오답 임계, 히스토리 (mascot-shop.md)."""

import time
from datetime import UTC, datetime

from app.models import ReviewCard, ReviewLog
from app.models.user import User, UserSettings
from app.services.game import typing_race as tr
from app.services.game.typing_race import wrong_threshold
from tests.test_game_manager import Collector, wired_db  # noqa: F401
from tests.test_study import login, seed_items
from tests.test_typing_race import seed_sentences


def test_wrong_threshold_forgives_single_typos():
    """철자 한둘 실수는 "틀린 문장"이 아니다 (2026-08-11 보고 — 동기 저하)."""
    assert wrong_threshold(20) == 2  # 짧은 문장도 오타 1개는 완성으로 인정
    assert wrong_threshold(40) == 2
    assert wrong_threshold(80) == 4  # 5% 기준
    assert wrong_threshold(0) == 2


async def test_done_records_wrong_only_over_threshold():
    """오타 1개 완성은 복습 회수 안 함 — 임계(max(2, 5%)) 이상만."""
    sentence = "a" * 40
    mgr = tr.TypingRaceManager()
    session = tr.RaceSession(
        match_id=1,
        code=None,
        host_id=7,
        mode="solo",
        players=[tr.RacerState(user_id=7, name="n")],
        sentences=[
            {"item_id": 1, "en": sentence, "ko": ""},
            {"item_id": 2, "en": sentence, "ko": ""},
        ],
        started=True,
        round_no=0,
        round_started=time.monotonic(),
    )
    mgr.sessions[1] = session
    mgr.by_user[7] = 1

    await mgr.done(7, idx=0, chars=len(sentence), errors=1)
    assert session.players[0].wrong == []  # 오타 1 — 회수 안 함

    session.round_no = 1
    session.players[0].done_current = False
    await mgr.done(7, idx=1, chars=len(sentence), errors=2)
    assert session.players[0].wrong == [1]  # 임계(40자→2) 도달 — 회수


async def test_room_broadcast_includes_profiles(wired_db):  # noqa: F811
    user = User(google_sub="g-badge", email="badge@example.com", name="B", nickname="배지")
    wired_db.add(user)
    await wired_db.flush()
    wired_db.add(
        UserSettings(user_id=user.id, mascot_key="bricky", featured_achievement="first_review")
    )
    await wired_db.commit()
    await seed_sentences(wired_db)

    mgr = tr.TypingRaceManager()
    sender = Collector()
    code = await mgr.create(user.id, user.nickname, sender)
    assert code
    room = next(m for m in sender.messages if m["t"] == "tp.room")
    profile = room["profiles"][user.nickname]
    assert profile["mascot"] == "bricky"
    assert profile["title"] == "첫 걸음"  # first_review 칭호
    mgr.detach(user.id)


async def test_featured_achievement_patch_requires_earned(client, db_session):
    user = await login(client, db_session)
    res = await client.patch("/api/settings", json={"featured_achievement": "first_review"})
    assert res.status_code == 422  # 미달성 지정 거부

    items = await seed_items(db_session, count=1)
    card = ReviewCard(
        user_id=user.id, item_id=items[0].id, state="review", due_at=datetime.now(UTC)
    )
    db_session.add(card)
    await db_session.flush()
    db_session.add(
        ReviewLog(
            card_id=card.id,
            user_id=user.id,
            rating=3,
            correct=True,
            quiz_mode="choice_en2ko",
            state_before="review",
            reviewed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    res = await client.patch("/api/settings", json={"featured_achievement": "first_review"})
    assert res.status_code == 200
    assert res.json()["featured_achievement"] == "first_review"
    res = await client.patch("/api/settings", json={"featured_achievement": ""})
    assert res.json()["featured_achievement"] is None  # 해제
    res = await client.patch("/api/settings", json={"featured_achievement": "nope"})
    assert res.status_code == 404


async def test_typing_history_lists_my_recent_races(client, db_session):
    from app.models import TypingRace

    user = await login(client, db_session)
    db_session.add(
        TypingRace(
            mode="solo",
            status="finished",
            player1_id=user.id,
            p1_chars=300,
            stats={"p1": {"cpm": 210, "peak_cpm": 280, "accuracy": 0.94, "sentences": 10}},
            ended_at=datetime.now(UTC),
        )
    )
    db_session.add(
        TypingRace(
            mode="race",
            status="finished",
            player1_id=user.id,
            winner_id=user.id,
            stats={"p1": {"cpm": 190, "peak_cpm": 250, "accuracy": 0.9, "sentences": 8}},
            ended_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    res = await client.get("/api/game/typing/history")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 2
    race = next(i for i in items if i["mode"] == "race")
    assert race["outcome"] == "win"
    solo = next(i for i in items if i["mode"] == "solo")
    assert solo["outcome"] is None and solo["peak_cpm"] == 280
