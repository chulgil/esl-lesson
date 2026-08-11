"""구매 이력 원장 — 사용자별 품목·결제수단 기록 (docs/specs/mascot-shop.md 구매 이력).

xp_spends 는 지갑(가용 XP 차감) 원장, purchases 는 구매 내역(무엇을 언제
어떤 결제수단으로 얼마에) 원장 — 현금·카드 결제 도입 대비 (2026-08-11 요구).
"""

from app.models import ThemeSetting
from tests.test_study import login
from tests.test_theme_shop import _earn_xp


async def test_shop_purchase_writes_history_row(client, db_session):
    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=200)  # 2000 XP

    await client.post("/api/shop/purchase", json={"item_key": "mascot:bricky"})
    res = await client.get("/api/shop/purchases")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    row = items[0]
    assert row["item_key"] == "mascot:bricky"
    assert row["method"] == "xp"
    assert row["currency"] == "XP"
    assert row["amount"] == 1500
    assert row["created_at"]


async def test_theme_and_saver_purchases_write_history(client, db_session):
    user = await login(client, db_session)
    db_session.add(ThemeSetting(theme_key="ocean", access="restricted", price_xp=500))
    await db_session.commit()
    await _earn_xp(db_session, user.id, reviews=200)  # 2000 XP

    assert (await client.post("/api/themes/ocean/purchase")).status_code == 200
    assert (await client.post("/api/shop/streak-saver/purchase")).status_code == 200

    items = (await client.get("/api/shop/purchases")).json()["items"]
    by_key = {i["item_key"]: i for i in items}
    assert by_key["theme:ocean"]["amount"] == 500
    assert by_key["saver:streak"]["amount"] == 500
    assert all(i["method"] == "xp" for i in items)


async def test_history_is_mine_only_and_newest_first(client, db_session):
    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=300)  # 3000 XP

    await client.post("/api/shop/purchase", json={"item_key": "outfit:ribbon"})
    await client.post("/api/shop/purchase", json={"item_key": "outfit:crown"})

    items = (await client.get("/api/shop/purchases")).json()["items"]
    assert [i["item_key"] for i in items] == ["outfit:crown", "outfit:ribbon"]

    # 실패한 구매(중복)는 이력에 남지 않는다
    dup = await client.post("/api/shop/purchase", json={"item_key": "outfit:ribbon"})
    assert dup.status_code == 409
    assert len((await client.get("/api/shop/purchases")).json()["items"]) == 2
