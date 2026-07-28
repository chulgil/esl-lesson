"""오늘의 목표 — 달성 가능한 소량 고정 목표 (포기 방지 기획, 2026-07-15).

밀린 전체(due)가 아니라 사용자 목표량 기준으로 진행을 보여주고,
리마인더도 "목표까지 남은 소량"으로 유도한다.
"""

from datetime import UTC, datetime

from app.services import push
from tests.test_push import SUB_BODY, _add_due_card
from tests.test_study import login, seed_items


async def test_daily_goal_setting_roundtrip(client, db_session):
    await login(client, db_session)
    res = await client.get("/api/settings")
    assert res.json()["daily_goal"] == 20  # 기본값

    res = await client.patch("/api/settings", json={"daily_goal": 10})
    assert res.status_code == 200
    assert res.json()["daily_goal"] == 10

    assert (await client.patch("/api/settings", json={"daily_goal": 3})).status_code == 422


async def test_stats_include_daily_goal(client, db_session):
    await login(client, db_session)
    res = await client.get("/api/study/stats")
    assert res.json()["daily_goal"] == 20


async def _log_today(db, user_id: int, count: int) -> None:
    from app.models import ReviewCard, ReviewLog

    items = await seed_items(db, count=1)
    card = ReviewCard(
        user_id=user_id, item_id=items[0].id, state="review", due_at=datetime.now(UTC)
    )
    db.add(card)
    await db.flush()
    for _ in range(count):
        db.add(
            ReviewLog(
                card_id=card.id,
                user_id=user_id,
                rating=3,
                correct=True,
                quiz_mode="choice_en2ko",
                state_before="review",
                reviewed_at=datetime.now(UTC),
            )
        )
    await db.flush()


async def test_reminder_message_is_goal_remainder_not_full_backlog(
    client,
    db_session,
    vapid_keys,
    monkeypatch,  # noqa: F811
):
    """밀린 30개여도 리마인더는 '목표까지 M개' — 겁주지 않는다."""
    user = await login(client, db_session)
    await _add_due_card(db_session, user.id, count=30)
    await client.post("/api/push/subscriptions", json=SUB_BODY)

    sent: list[dict] = []

    async def fake_send(sub, payload, settings):
        sent.append(payload)
        return "ok"

    monkeypatch.setattr(push, "send_to", fake_send)
    evening = datetime.now(UTC).astimezone(push.KST).replace(hour=20, minute=30)
    assert await push.send_review_reminders(db_session, now=evening.astimezone(UTC)) == 1
    assert "20개" in sent[0]["body"]  # min(due 30, 목표 20 잔여)
    assert "30개" not in sent[0]["body"]


async def test_reminder_skipped_when_goal_met(
    client,
    db_session,
    vapid_keys,
    monkeypatch,  # noqa: F811
):
    """오늘 목표를 이미 채운 사용자에게는 발송하지 않는다 — 달성감 보존."""
    user = await login(client, db_session)
    await _add_due_card(db_session, user.id, count=5)
    await _log_today(db_session, user.id, count=20)  # 목표(기본 20) 달성
    await client.post("/api/push/subscriptions", json=SUB_BODY)

    sent: list[dict] = []

    async def fake_send(sub, payload, settings):
        sent.append(payload)
        return "ok"

    monkeypatch.setattr(push, "send_to", fake_send)
    evening = datetime.now(UTC).astimezone(push.KST).replace(hour=20, minute=30)
    assert await push.send_review_reminders(db_session, now=evening.astimezone(UTC)) == 0
    assert sent == []
