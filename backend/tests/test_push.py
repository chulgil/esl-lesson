"""웹 푸시 리마인더 P3 — 구독 관리 + 일일 발송 로직 (docs/specs/push-reminder.md)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import PushSubscription, ReviewCard
from app.services import push
from tests.test_study import login, seed_items

SUB_BODY = {
    "endpoint": "https://push.example.com/sub/abc",
    "keys": {"p256dh": "pkey", "auth": "akey"},
}


async def _add_due_card(db, user_id: int, count: int = 1) -> None:
    """가시성 규칙 통과(공용 콘텐츠 출처)하는 밀린 카드 생성."""
    items = await seed_items(db, count=count)
    for item in items:
        db.add(
            ReviewCard(
                user_id=user_id,
                item_id=item.id,
                state="review",
                due_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
    await db.flush()


async def test_config_disabled_without_keys(client):
    res = await client.get("/api/push/config")
    assert res.status_code == 200
    assert res.json() == {"enabled": False, "public_key": ""}


async def test_config_exposes_public_key(client, vapid_keys):
    res = await client.get("/api/push/config")
    assert res.json() == {"enabled": True, "public_key": "test-public-key"}


async def test_subscribe_requires_auth(client):
    res = await client.post("/api/push/subscriptions", json=SUB_BODY)
    assert res.status_code == 401


async def test_subscribe_upserts_by_endpoint(client, db_session):
    user = await login(client, db_session)
    res = await client.post("/api/push/subscriptions", json=SUB_BODY)
    assert res.status_code == 200

    # 같은 endpoint 재구독 = 갱신 (중복 행 금지)
    res = await client.post(
        "/api/push/subscriptions",
        json={**SUB_BODY, "keys": {"p256dh": "pkey2", "auth": "akey2"}},
    )
    assert res.status_code == 200
    rows = (await db_session.execute(select(PushSubscription))).scalars().all()
    assert len(rows) == 1
    assert rows[0].user_id == user.id
    assert rows[0].p256dh == "pkey2"


async def test_unsubscribe_deletes_own_row(client, db_session):
    await login(client, db_session)
    await client.post("/api/push/subscriptions", json=SUB_BODY)
    res = await client.request(
        "DELETE", "/api/push/subscriptions", json={"endpoint": SUB_BODY["endpoint"]}
    )
    assert res.status_code == 200
    rows = (await db_session.execute(select(PushSubscription))).scalars().all()
    assert rows == []


async def test_subscribe_rejects_non_https_endpoint(client, db_session):
    await login(client, db_session)
    res = await client.post(
        "/api/push/subscriptions",
        json={"endpoint": "http://insecure.example.com/x", "keys": SUB_BODY["keys"]},
    )
    assert res.status_code == 422


async def test_reminder_sends_once_per_day_to_due_users(
    client, db_session, vapid_keys, monkeypatch
):
    """20시 KST 이후, 밀린 복습 있는 구독자에게 하루 1회만 발송."""
    user = await login(client, db_session)
    await _add_due_card(db_session, user.id, count=3)
    await client.post("/api/push/subscriptions", json=SUB_BODY)

    sent: list[dict] = []

    async def fake_send(sub, payload, settings):
        sent.append(payload)
        return "ok"

    monkeypatch.setattr(push, "send_to", fake_send)
    evening = datetime.now(UTC).astimezone(push.KST).replace(hour=20, minute=30)

    count = await push.send_review_reminders(db_session, now=evening.astimezone(UTC))
    await db_session.commit()
    assert count == 1
    assert "3개" in sent[0]["body"]
    assert sent[0]["url"] == "/study/session"

    # 같은 날 재실행 — 발송 없음 (last_sent_on dedup)
    count = await push.send_review_reminders(db_session, now=evening.astimezone(UTC))
    assert count == 0 and len(sent) == 1


async def test_reminder_skips_before_hour_and_zero_due(client, db_session, vapid_keys, monkeypatch):
    user = await login(client, db_session)
    await client.post("/api/push/subscriptions", json=SUB_BODY)
    sent: list[dict] = []

    async def fake_send(sub, payload, settings):
        sent.append(payload)
        return "ok"

    monkeypatch.setattr(push, "send_to", fake_send)

    # 20시 이전 — 발송 안 함
    morning = datetime.now(UTC).astimezone(push.KST).replace(hour=9, minute=0)
    assert await push.send_review_reminders(db_session, now=morning.astimezone(UTC)) == 0

    # 20시 이후지만 밀린 복습 0 — 발송 안 함 + dedup 마킹도 안 함 (이후 due 생기면 발송)
    evening = datetime.now(UTC).astimezone(push.KST).replace(hour=21, minute=0)
    assert await push.send_review_reminders(db_session, now=evening.astimezone(UTC)) == 0
    assert sent == []

    await _add_due_card(db_session, user.id)
    assert await push.send_review_reminders(db_session, now=evening.astimezone(UTC)) == 1


async def test_reminder_removes_gone_subscription(client, db_session, vapid_keys, monkeypatch):
    """푸시 서비스가 404/410 반환 = 만료 구독 — 행 삭제."""
    user = await login(client, db_session)
    await _add_due_card(db_session, user.id)
    await client.post("/api/push/subscriptions", json=SUB_BODY)

    async def gone_send(sub, payload, settings):
        return "gone"

    monkeypatch.setattr(push, "send_to", gone_send)
    evening = datetime.now(UTC).astimezone(push.KST).replace(hour=20, minute=5)
    assert await push.send_review_reminders(db_session, now=evening.astimezone(UTC)) == 0
    await db_session.commit()
    rows = (await db_session.execute(select(PushSubscription))).scalars().all()
    assert rows == []


async def test_reminder_transient_error_keeps_sub_and_retries(
    client, db_session, vapid_keys, monkeypatch
):
    """일시 오류(403 등)는 구독 유지 + 발송 마킹 안 함 — 다음 루프에서 재시도.

    이전엔 오류가 True 로 뭉개져 last_sent_on 이 찍혀 그날 재시도가 막혔다."""
    user = await login(client, db_session)
    await _add_due_card(db_session, user.id)
    await client.post("/api/push/subscriptions", json=SUB_BODY)

    async def error_send(sub, payload, settings):
        return "error"

    monkeypatch.setattr(push, "send_to", error_send)
    evening = datetime.now(UTC).astimezone(push.KST).replace(hour=20, minute=5)
    assert await push.send_review_reminders(db_session, now=evening.astimezone(UTC)) == 0
    await db_session.commit()
    rows = (await db_session.execute(select(PushSubscription))).scalars().all()
    assert len(rows) == 1 and rows[0].last_sent_on is None  # 유지 + 미마킹

    # 복구되면 같은 날에도 발송된다
    async def ok_send(sub, payload, settings):
        return "ok"

    monkeypatch.setattr(push, "send_to", ok_send)
    assert await push.send_review_reminders(db_session, now=evening.astimezone(UTC)) == 1


async def test_push_test_endpoint_reports_errors_honestly(
    client, db_session, vapid_keys, monkeypatch
):
    """발송 실패는 sent 가 아니라 errors 로 보고 — '보냈어요' 거짓 안내 방지."""
    await login(client, db_session)
    await client.post("/api/push/subscriptions", json=SUB_BODY)

    async def error_send(sub, payload, settings):
        return "error"

    monkeypatch.setattr(push, "send_to", error_send)
    res = await client.post("/api/push/test")
    assert res.status_code == 200
    assert res.json() == {"sent": 0, "errors": 1}


async def test_push_test_endpoint_sends_to_my_devices(client, db_session, vapid_keys, monkeypatch):
    await login(client, db_session)
    await client.post("/api/push/subscriptions", json=SUB_BODY)
    sent: list[dict] = []

    async def fake_send(sub, payload, settings):
        sent.append(payload)
        return "ok"

    monkeypatch.setattr(push, "send_to", fake_send)
    res = await client.post("/api/push/test")
    assert res.status_code == 200
    assert res.json()["sent"] == 1
    assert len(sent) == 1


async def test_account_delete_removes_subscriptions(client, db_session):
    await login(client, db_session)
    await client.post("/api/push/subscriptions", json=SUB_BODY)
    res = await client.delete("/api/me")
    assert res.status_code == 204
    rows = (await db_session.execute(select(PushSubscription))).scalars().all()
    assert rows == []
