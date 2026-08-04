"""푸시 시각 개인화(실행 의도) + 내일 예고 due_tomorrow.

기획: docs/proposal/user-journey-motivation-2026-08.md P1 / 스펙: push-reminder.md, learning.md
"""

from datetime import UTC, datetime, timedelta

from app.services import push
from tests.test_push import SUB_BODY, _add_due_card
from tests.test_study import login, seed_items


async def test_settings_reminder_hour_roundtrip(client, db_session):
    await login(client, db_session)
    assert (await client.get("/api/settings")).json()["reminder_hour"] == 20

    res = await client.patch("/api/settings", json={"reminder_hour": 7})
    assert res.status_code == 200
    assert res.json()["reminder_hour"] == 7

    # 새벽 시간대는 금지 (5시 미만) — 알림 피로 방지
    assert (await client.patch("/api/settings", json={"reminder_hour": 3})).status_code == 422


async def test_reminder_sent_at_user_morning_hour(client, db_session, vapid_keys, monkeypatch):
    """아침형 사용자(7시)는 아침에 받는다 — 기존엔 20시 전 발송 불가."""
    user = await login(client, db_session)
    await _add_due_card(db_session, user.id, count=5)
    await client.post("/api/push/subscriptions", json=SUB_BODY)
    await client.patch("/api/settings", json={"reminder_hour": 7})

    sent: list[dict] = []

    async def fake_send(sub, payload, settings):
        sent.append(payload)
        return "ok"

    monkeypatch.setattr(push, "send_to", fake_send)
    # 내일 아침 07:30 — 카드 생성 시각(지금)보다 항상 미래라 due 가 결정적으로 잡힘
    morning = (datetime.now(UTC).astimezone(push.KST) + timedelta(days=1)).replace(
        hour=7, minute=30
    )
    assert await push.send_review_reminders(db_session, now=morning.astimezone(UTC)) == 1
    assert len(sent) == 1


async def test_reminder_waits_until_user_hour(client, db_session, vapid_keys, monkeypatch):
    """사용자가 21시로 미뤘으면 20시대엔 보내지 않는다."""
    user = await login(client, db_session)
    await _add_due_card(db_session, user.id, count=5)
    await client.post("/api/push/subscriptions", json=SUB_BODY)
    await client.patch("/api/settings", json={"reminder_hour": 21})

    sent: list[dict] = []

    async def fake_send(sub, payload, settings):
        sent.append(payload)
        return "ok"

    monkeypatch.setattr(push, "send_to", fake_send)
    # 내일 날짜 기준 — 실행 시각(KST 밤)과 무관하게 due 가 결정적으로 잡힘
    tomorrow = datetime.now(UTC).astimezone(push.KST) + timedelta(days=1)
    evening = tomorrow.replace(hour=20, minute=30)
    assert await push.send_review_reminders(db_session, now=evening.astimezone(UTC)) == 0
    late = tomorrow.replace(hour=21, minute=10)
    assert await push.send_review_reminders(db_session, now=late.astimezone(UTC)) == 1


async def test_stats_due_tomorrow(client, db_session):
    """내일 예고 — 지금은 아니지만 내일 안에 due 가 되는 카드 수."""
    from app.models import ReviewCard

    user = await login(client, db_session)
    items = await seed_items(db_session, count=3)
    now = datetime.now(UTC)
    for item, due in (
        (items[0], now + timedelta(hours=1)),  # 내일 창 안
        (items[1], now + timedelta(days=3)),  # 창 밖
        (items[2], now - timedelta(hours=1)),  # 이미 due — due_count 몫
    ):
        db_session.add(
            ReviewCard(user_id=user.id, item_id=item.id, state="review", due_at=due, reps=1)
        )
    await db_session.commit()

    data = (await client.get("/api/study/stats")).json()
    assert data["due_tomorrow"] == 1
    assert data["due_count"] == 1
