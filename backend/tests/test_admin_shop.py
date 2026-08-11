"""백오피스 캐릭터 상점 — 가격 오버라이드·이벤트 한정·수동 지급 (mascot-shop.md).

테마 몰과 같은 관리 모델: 가격은 item_settings 오버라이드(NULL=카탈로그 기본가),
sale="event" 는 XP 구매 차단(이벤트 지급 전용), 지급/회수는 item_grants 행.

admin_client 는 같은 클라이언트에 admin 쿠키를 씌운 것 — login() 이 쿠키를
덮어쓰므로 역할 전환은 세션 쿠키 스위칭으로 한다.
"""

from sqlalchemy import func, select

from app.core.security import SESSION_COOKIE
from app.models import ItemGrant
from tests.test_study import login
from tests.test_theme_shop import _earn_xp


def _token(client) -> str:
    return client.cookies.get(SESSION_COOKIE)


def _use(client, token: str) -> None:
    client.cookies.set(SESSION_COOKIE, token)


async def test_admin_only_and_catalog_lists_settings(admin_client, client, db_session):
    res = await admin_client.get("/api/admin/shop")
    assert res.status_code == 200
    items = {i["key"]: i for i in res.json()["items"]}
    assert items["mascot:bricky"]["price_xp"] == 1500  # 카탈로그 기본가
    assert items["mascot:bricky"]["sale"] == "xp"
    assert items["outfit:ribbon"]["kind"] == "outfit"
    assert items["mascot:bricky"]["grants"] == 0

    await login(client, db_session)  # 일반 사용자로 전환
    assert (await client.get("/api/admin/shop")).status_code == 403


async def test_price_override_applies_to_shop_and_purchase(admin_client, client, db_session):
    admin_token = _token(admin_client)
    res = await admin_client.patch("/api/admin/shop/outfit:ribbon", json={"price_xp": 700})
    assert res.status_code == 200 and res.json()["price_xp"] == 700

    user = await login(client, db_session)
    user_token = _token(client)
    await _earn_xp(db_session, user.id, reviews=100)  # 1000 XP

    shop = (await client.get("/api/shop")).json()
    ribbon = next(o for o in shop["outfits"] if o["key"] == "ribbon")
    assert ribbon["price_xp"] == 700

    res = await client.post("/api/shop/purchase", json={"item_key": "outfit:ribbon"})
    assert res.status_code == 200 and res.json()["available_xp"] == 300
    history = (await client.get("/api/shop/purchases")).json()["items"]
    assert history[0]["amount"] == 700

    # NULL = 기본가 복귀
    _use(client, admin_token)
    res = await client.patch("/api/admin/shop/outfit:ribbon", json={"price_xp": None})
    assert res.status_code == 200 and res.json()["price_xp"] == 300
    _use(client, user_token)
    shop = (await client.get("/api/shop")).json()
    assert next(o for o in shop["outfits"] if o["key"] == "ribbon")["price_xp"] == 300


async def test_event_only_blocks_xp_purchase(admin_client, client, db_session):
    admin_token = _token(admin_client)
    res = await admin_client.patch("/api/admin/shop/mascot:henyang", json={"sale": "event"})
    assert res.status_code == 200 and res.json()["sale"] == "event"

    user = await login(client, db_session)
    user_token = _token(client)
    await _earn_xp(db_session, user.id, reviews=300)  # 3000 XP — 잔액 충분해도 차단

    shop = (await client.get("/api/shop")).json()
    assert next(m for m in shop["mascots"] if m["key"] == "henyang")["sale"] == "event"
    res = await client.post("/api/shop/purchase", json={"item_key": "mascot:henyang"})
    assert res.status_code == 422 and res.json()["detail"] == "event_only_item"

    # XP 판매로 되돌리면 다시 구매 가능
    _use(client, admin_token)
    assert (
        await client.patch("/api/admin/shop/mascot:henyang", json={"sale": "xp"})
    ).status_code == 200
    _use(client, user_token)
    res = await client.post("/api/shop/purchase", json={"item_key": "mascot:henyang"})
    assert res.status_code == 200


async def test_admin_grant_and_revoke(admin_client, client, db_session):
    admin_token = _token(admin_client)
    await login(client, db_session, email="s@example.com")
    user_token = _token(client)

    _use(client, admin_token)
    res = await client.post(
        "/api/admin/shop/mascot:mongi/grants",
        json={"email": "s@example.com", "note": "여름 이벤트"},
    )
    assert res.status_code == 200
    grant_id = res.json()["id"]
    dup = await client.post("/api/admin/shop/mascot:mongi/grants", json={"email": "s@example.com"})
    assert dup.status_code == 409
    missing = await client.post(
        "/api/admin/shop/hat:fedora/grants", json={"email": "s@example.com"}
    )
    assert missing.status_code == 404

    _use(client, user_token)
    shop = (await client.get("/api/shop")).json()
    assert next(m for m in shop["mascots"] if m["key"] == "mongi")["owned"] is True
    # 지급은 구매가 아니다 — 구매 이력에 남지 않는다
    assert (await client.get("/api/shop/purchases")).json()["items"] == []
    # 지급받은 마스코트는 활성화 가능
    assert (await client.patch("/api/shop/mascot", json={"key": "mongi"})).status_code == 200

    _use(client, admin_token)
    assert (await client.delete(f"/api/admin/shop/grants/{grant_id}")).status_code == 204
    _use(client, user_token)
    shop = (await client.get("/api/shop")).json()
    assert next(m for m in shop["mascots"] if m["key"] == "mongi")["owned"] is False
    # 활성 마스코트 회수 → 활성도 해제 — 좌하단·플레이어 배지에 남으면 안 된다
    assert shop["active_mascot"] is None


async def test_admin_grant_race_returns_409_not_500(admin_client, client, db_session, monkeypatch):
    """동시 지급(백오피스 더블클릭 등) — 두 요청 다 '미지급'으로 보고 flush 하면
    두 번째는 uq_item_grants_user_key 위반으로 500 이 날 수 있다. 409 로
    흡수해야 한다 (2026-08-11 픽스)."""
    from app.api import admin_shop as admin_shop_api

    admin_token = _token(admin_client)
    user = await login(client, db_session, email="racer@example.com")
    user_id = user.id  # create_grant 내부 rollback 이 user 를 만료시키므로 캡처
    _use(client, admin_token)

    async def fake_not_duplicate(db, user_id, item_key):
        return False  # 동시 요청이 아직 커밋 전이라 못 본 것처럼

    monkeypatch.setattr(admin_shop_api, "_duplicate_item_grant", fake_not_duplicate)

    # 다른 동시 지급 요청이 이미 커밋을 마친 상태
    db_session.add(ItemGrant(user_id=user_id, item_key="mascot:mongi", note="선착 지급"))
    await db_session.commit()

    res = await client.post(
        "/api/admin/shop/mascot:mongi/grants", json={"email": "racer@example.com"}
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "already_granted"

    count = (
        await db_session.execute(
            select(func.count(ItemGrant.id)).where(
                ItemGrant.user_id == user_id, ItemGrant.item_key == "mascot:mongi"
            )
        )
    ).scalar_one()
    assert count == 1
