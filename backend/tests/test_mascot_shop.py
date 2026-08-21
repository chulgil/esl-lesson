"""마스코트 상점 — 구매·활성·책갈피 충전 (docs/specs/mascot-shop.md)."""

from app.models import ItemGrant, XpSpend
from app.services import progress as progress_service
from tests.test_study import login
from tests.test_theme_shop import _earn_xp


def _stale_then_real_available_xp(stale_value: int):
    """사전 검증(1회차)은 오래된 값을, 이후 호출은 실제 값을 반환 — TOCTOU 경합 재현.

    커밋 후 재검증 훅(progress.revert_if_overdrawn)도 같은 함수를 호출하므로
    2회차부터는 실제 값으로 동시 구매 반영분을 정확히 잡아낸다.
    """
    real_available_xp = progress_service.available_xp
    calls = {"n": 0}

    async def fake(db, user_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return stale_value
        return await real_available_xp(db, user_id)

    return fake


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


async def test_purchase_item_reverts_on_toctou_race(client, db_session, monkeypatch):
    """사전 잔액검증과 커밋 사이 다른 구매가 끼어드는 경합 — 커밋 후 재검증으로
    가용 XP 음수를 잡아내고 방금 산 아이템을 되돌린다 (2026-08-11 TOCTOU 픽스)."""
    from app.api import shop as shop_api

    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=200)  # 2000 XP

    # 동시에 이미 커밋된 다른 구매(마스코트 1500) — 실제 가용 XP 는 500
    db_session.add(XpSpend(user_id=user.id, amount=1500, reason="mascot:mongi"))
    db_session.add(ItemGrant(user_id=user.id, item_key="mascot:mongi", note="XP 구매"))
    await db_session.commit()

    monkeypatch.setattr(shop_api.progress, "available_xp", _stale_then_real_available_xp(2000))

    res = await client.post("/api/shop/purchase", json={"item_key": "outfit:crown"})  # 1000 XP
    assert res.status_code == 422
    assert res.json()["detail"] == "insufficient_xp"

    shop = (await client.get("/api/shop")).json()
    assert next(o for o in shop["outfits"] if o["key"] == "crown")["owned"] is False
    assert shop["available_xp"] == 500  # 동시 구매분만 반영, 방금 시도는 되돌림


async def test_streak_saver_purchase_reverts_on_toctou_race(client, db_session, monkeypatch):
    from app.api import shop as shop_api

    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=200)  # 2000 XP

    db_session.add(XpSpend(user_id=user.id, amount=1600, reason="mascot:henyang"))
    await db_session.commit()

    monkeypatch.setattr(shop_api.progress, "available_xp", _stale_then_real_available_xp(2000))

    res = await client.post("/api/shop/streak-saver/purchase")
    assert res.status_code == 422
    assert res.json()["detail"] == "insufficient_xp"

    shop = (await client.get("/api/shop")).json()
    assert shop["streak_saver"]["count"] == 0  # 증가분 되돌림
    assert shop["available_xp"] == 400  # 동시 구매분만 반영


async def test_message_ticket_purchase_and_consume(client, db_session):
    """말풍선 변경권 — 구매(카운터 증가) → 문구 변경(1개 소모) → 검증·복귀
    (2026-08-21, mascot-shop.md §말풍선 변경권)."""
    user = await login(client, db_session)

    # 변경권 없이 변경 시도 → no_ticket
    res = await client.patch("/api/shop/mascot-message", json={"message": "화이팅"})
    assert res.status_code == 422
    assert res.json()["detail"] == "no_ticket"

    # perk 는 일반 구매 엔드포인트로 살 수 없다 (카운터 상품)
    res = await client.post("/api/shop/purchase", json={"item_key": "perk:message"})
    assert res.status_code == 404

    await _earn_xp(db_session, user.id, 1000)
    res = await client.post("/api/shop/message-ticket/purchase")
    assert res.status_code == 200
    assert res.json()["count"] == 1

    # 유효성 — 7자·공백만 422
    for bad in ("일곱글자라서안돼", "   "):
        res = await client.patch("/api/shop/mascot-message", json={"message": bad})
        assert res.status_code == 422

    res = await client.patch("/api/shop/mascot-message", json={"message": "화이팅!"})
    assert res.status_code == 200
    assert res.json() == {"message": "화이팅!", "tickets": 0}

    shop = (await client.get("/api/shop")).json()
    assert shop["message_ticket"]["current_message"] == "화이팅!"
    assert shop["message_ticket"]["count"] == 0

    # 기본 복귀는 무료 (변경권 0개여도 가능)
    res = await client.patch("/api/shop/mascot-message", json={"message": None})
    assert res.status_code == 200
    assert res.json()["message"] is None


async def test_outfit_worn_toggle(client, db_session):
    """악세 착용 토글 (2026-08-21) — 기본 all-on, 해제 후 worn=False,
    비보유 403, 착용 목록 관리 중 새 구매는 자동 착용."""
    user = await login(client, db_session)
    db_session.add(ItemGrant(user_id=user.id, item_key="outfit:ribbon", note="test"))
    await db_session.commit()

    shop = (await client.get("/api/shop")).json()
    ribbon = next(o for o in shop["outfits"] if o["key"] == "ribbon")
    assert ribbon["worn"] is True  # NULL = 보유분 전부 착용 (구 all-on 보존)

    res = await client.patch("/api/shop/outfit", json={"key": "ribbon", "worn": False})
    assert res.status_code == 200
    assert res.json()["outfits_worn"] == []
    shop = (await client.get("/api/shop")).json()
    assert next(o for o in shop["outfits"] if o["key"] == "ribbon")["worn"] is False

    # 비보유 악세는 403
    res = await client.patch("/api/shop/outfit", json={"key": "crown", "worn": True})
    assert res.status_code == 403

    # 착용 목록 관리 중 새 구매 → 자동 착용
    await _earn_xp(db_session, user.id, 1000)
    res = await client.post("/api/shop/purchase", json={"item_key": "outfit:glasses"})
    assert res.status_code == 200
    shop = (await client.get("/api/shop")).json()
    assert next(o for o in shop["outfits"] if o["key"] == "glasses")["worn"] is True
    assert next(o for o in shop["outfits"] if o["key"] == "ribbon")["worn"] is False
