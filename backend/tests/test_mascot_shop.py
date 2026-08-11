"""마스코트 상점 — 구매·활성·책갈피 충전 (docs/specs/mascot-shop.md)."""

from tests.test_study import login
from tests.test_theme_shop import _earn_xp


async def test_catalog_lists_items_and_wallet(client, db_session):
    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=10)  # 100 XP

    shop = (await client.get("/api/shop")).json()
    assert shop["available_xp"] == 100
    assert shop["active_mascot"] is None
    assert {m["key"] for m in shop["mascots"]} == {"henyang", "bricky", "mongi"}
    assert {o["key"] for o in shop["outfits"]} == {"ribbon", "glasses", "scarf", "crown"}
    assert all(m["owned"] is False for m in shop["mascots"])
    assert shop["streak_saver"]["price_xp"] == 500


async def test_purchase_mascot_auto_activates(client, db_session):
    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=200)  # 2000 XP

    res = await client.post("/api/shop/purchase", json={"item_key": "mascot:bricky"})
    assert res.status_code == 200
    body = res.json()
    assert body["available_xp"] == 500
    assert body["active_mascot"] == "bricky"  # 산 즉시 화면에 나타난다

    shop = (await client.get("/api/shop")).json()
    assert next(m for m in shop["mascots"] if m["key"] == "bricky")["owned"] is True
    # 중복 구매 차단
    dup = await client.post("/api/shop/purchase", json={"item_key": "mascot:bricky"})
    assert dup.status_code == 409


async def test_purchase_requires_balance_and_known_item(client, db_session):
    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=10)  # 100 XP — 리본(300)도 부족

    res = await client.post("/api/shop/purchase", json={"item_key": "outfit:ribbon"})
    assert res.status_code == 422
    res = await client.post("/api/shop/purchase", json={"item_key": "hat:fedora"})
    assert res.status_code == 404


async def test_outfit_purchase_keeps_active_mascot(client, db_session):
    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=300)  # 3000 XP
    await client.post("/api/shop/purchase", json={"item_key": "mascot:mongi"})

    res = await client.post("/api/shop/purchase", json={"item_key": "outfit:ribbon"})
    assert res.status_code == 200
    assert res.json()["active_mascot"] == "mongi"  # 악세 구매는 활성 마스코트 유지


async def test_set_mascot_requires_ownership(client, db_session):
    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=150)  # 1500 XP

    res = await client.patch("/api/shop/mascot", json={"key": "henyang"})
    assert res.status_code == 403  # 미보유
    res = await client.patch("/api/shop/mascot", json={"key": "unknown"})
    assert res.status_code == 404

    await client.post("/api/shop/purchase", json={"item_key": "mascot:bricky"})
    res = await client.patch("/api/shop/mascot", json={"key": None})  # 끄기
    assert res.status_code == 200 and res.json()["active_mascot"] is None
    res = await client.patch("/api/shop/mascot", json={"key": "bricky"})
    assert res.status_code == 200 and res.json()["active_mascot"] == "bricky"


async def test_streak_saver_purchase_caps_at_max(client, db_session):
    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=200)  # 2000 XP

    assert (await client.post("/api/shop/streak-saver/purchase")).json()["count"] == 1
    assert (await client.post("/api/shop/streak-saver/purchase")).json()["count"] == 2
    res = await client.post("/api/shop/streak-saver/purchase")
    assert res.status_code == 422  # SAVER_MAX=2

    shop = (await client.get("/api/shop")).json()
    assert shop["available_xp"] == 1000  # 500 x 2 차감
    assert shop["streak_saver"]["count"] == 2
