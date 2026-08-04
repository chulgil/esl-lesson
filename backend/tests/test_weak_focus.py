"""오답 정리 모드(?mode=weak) + 장기 기억 지표 — 개인화 학습과학 팩.

기획: docs/proposal/duolingo-benchmark-2026-08.md / 스펙: docs/specs/learning.md
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import ReviewCard, ReviewLog
from tests.test_study import login, seed_items


async def _card_with_log(
    db,
    user_id: int,
    item_id: int,
    *,
    correct: bool,
    days_ago: float,
    stability: float | None = None,
    state: str = "review",
    suspended: bool = False,
    scheduled_days: float | None = None,
):
    now = datetime.now(UTC)
    card = ReviewCard(
        user_id=user_id,
        item_id=item_id,
        state=state,
        due_at=now + timedelta(days=1),  # due 아님 — weak 모드는 due 무관 출제
        stability=stability,
        suspended=suspended,
        reps=1,
    )
    db.add(card)
    await db.flush()
    db.add(
        ReviewLog(
            card_id=card.id,
            user_id=user_id,
            rating=3 if correct else 1,
            correct=correct,
            quiz_mode="choice_en2ko",
            state_before=state,
            scheduled_days=scheduled_days,
            reviewed_at=now - timedelta(days=days_ago),
        )
    )
    await db.commit()
    return card


async def test_weak_queue_returns_only_recent_wrong_cards(client, db_session):
    user = await login(client, db_session)
    items = await seed_items(db_session, count=4)

    wrong_recent = await _card_with_log(
        db_session, user.id, items[0].id, correct=False, days_ago=2, stability=2.0
    )
    await _card_with_log(db_session, user.id, items[1].id, correct=True, days_ago=2)
    await _card_with_log(db_session, user.id, items[2].id, correct=False, days_ago=10)
    await _card_with_log(
        db_session, user.id, items[3].id, correct=False, days_ago=1, suspended=True
    )

    res = await client.get("/api/study/queue?mode=weak")
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "weak"
    assert data["introduced_today"] == 0
    assert [q["card_id"] for q in data["questions"]] == [wrong_recent.id]


async def test_weak_queue_orders_by_stability_and_skips_new_intro(client, db_session):
    user = await login(client, db_session)
    items = await seed_items(db_session, count=4)  # [3]은 카드 없는 신규 후보

    mid = await _card_with_log(
        db_session, user.id, items[0].id, correct=False, days_ago=1, stability=5.0
    )
    unknown = await _card_with_log(
        db_session, user.id, items[1].id, correct=False, days_ago=1, stability=None
    )
    shaky = await _card_with_log(
        db_session, user.id, items[2].id, correct=False, days_ago=1, stability=1.0
    )

    res = await client.get("/api/study/queue?mode=weak")
    assert [q["card_id"] for q in res.json()["questions"]] == [
        unknown.id,
        shaky.id,
        mid.id,
    ]

    # 신규 도입 없음 — 카드 없는 항목(items[3])에 카드가 생기지 않는다
    total_cards = (
        await db_session.execute(
            select(func.count(ReviewCard.id)).where(ReviewCard.user_id == user.id)
        )
    ).scalar_one()
    assert total_cards == 3


async def test_stats_include_weak_count_and_long_term(client, db_session):
    user = await login(client, db_session)
    items = await seed_items(db_session, count=5)

    # 오답 정리 대상 2개 (최근 오답), 1개는 창 밖(10일 전)
    await _card_with_log(db_session, user.id, items[0].id, correct=False, days_ago=1, stability=2.0)
    await _card_with_log(db_session, user.id, items[1].id, correct=False, days_ago=3, stability=1.0)
    await _card_with_log(db_session, user.id, items[2].id, correct=False, days_ago=10)

    # 장기 기억: stability 10 (도달 3주 전 로그) — 카운트 1
    await _card_with_log(
        db_session,
        user.id,
        items[3].id,
        correct=True,
        days_ago=21,
        stability=10.0,
        scheduled_days=10.0,
    )
    # suspended 는 장기 기억에서 제외
    await _card_with_log(
        db_session,
        user.id,
        items[4].id,
        correct=True,
        days_ago=1,
        stability=20.0,
        suspended=True,
    )

    res = await client.get("/api/study/stats")
    data = res.json()
    assert data["weak_count"] == 2
    assert data["long_term"]["count"] == 1
    weekly = data["long_term"]["weekly"]
    assert len(weekly) == 8
    assert weekly[0]["count"] == 0  # 8주 전에는 도달 카드 없음
    assert weekly[-1]["count"] == 1  # 3주 전 도달 → 현재 주 누적 1
