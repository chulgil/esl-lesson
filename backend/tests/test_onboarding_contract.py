"""첫 주 계약 온보딩 — 리마인더 설정 완료를 서버에서 판정한다.

기획: docs/proposal/effectiveness-audit-2026-08.md 구멍 4 / 스펙: ui-design.md
"""

from tests.test_push import SUB_BODY
from tests.test_study import login


async def test_settings_push_subscribed_follows_subscription(client, db_session):
    """구독 전 False → 구독 후 True → 해제 후 False (기기 존재 여부 파생)."""
    await login(client, db_session)
    assert (await client.get("/api/settings")).json()["push_subscribed"] is False

    await client.post("/api/push/subscriptions", json=SUB_BODY)
    assert (await client.get("/api/settings")).json()["push_subscribed"] is True

    await client.request(
        "DELETE", "/api/push/subscriptions", json={"endpoint": SUB_BODY["endpoint"]}
    )
    assert (await client.get("/api/settings")).json()["push_subscribed"] is False


async def test_settings_patch_keeps_push_subscribed(client, db_session):
    """PATCH 응답도 같은 shape — 저장 직후 체크리스트가 단계를 잃지 않는다."""
    await login(client, db_session)
    await client.post("/api/push/subscriptions", json=SUB_BODY)

    res = await client.patch("/api/settings", json={"reminder_hour": 7})
    assert res.status_code == 200
    assert res.json()["push_subscribed"] is True


async def test_settings_push_subscribed_is_per_user(client, db_session):
    """다른 유저의 구독은 내 완료 판정에 섞이지 않는다."""
    await login(client, db_session)
    await client.post("/api/push/subscriptions", json=SUB_BODY)

    await login(client, db_session, email="other@example.com")
    assert (await client.get("/api/settings")).json()["push_subscribed"] is False
