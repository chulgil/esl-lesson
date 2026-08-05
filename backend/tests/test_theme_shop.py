"""XP 상점 — 테마 구매 (docs/specs/theme-mall.md XP 상점, 2026-08-05).

규칙: 가격은 백오피스 입력(theme_settings.price_xp, NULL=미판매), 업적/이벤트
보상 규칙이 있는 테마는 판매·가격설정 모두 거부, 가용 XP = 누적 - 소비.
"""

from datetime import UTC, datetime

from app.models import ReviewCard, ReviewLog, ThemeRewardRule
from tests.test_study import login, seed_items


async def _earn_xp(db, user_id: int, reviews: int) -> None:
    """복습 로그로 XP 적립 — 복습 1건 = 10 XP."""
    items = await seed_items(db, count=1)
    card = ReviewCard(
        user_id=user_id, item_id=items[0].id, state="review", due_at=datetime.now(UTC)
    )
    db.add(card)
    await db.flush()
    for _ in range(reviews):
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
    await db.commit()


async def test_admin_sets_price_and_user_purchases(admin_client, client, db_session):
    await admin_client.patch("/api/admin/themes/ocean/price", json={"price_xp": 500})

    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=60)  # 600 XP

    listing = (await client.get("/api/themes")).json()
    ocean = next(i for i in listing["items"] if i["key"] == "ocean")
    assert ocean["price_xp"] == 500
    assert ocean["allowed"] is False
    assert listing["available_xp"] == 600

    res = await client.post("/api/themes/ocean/purchase")
    assert res.status_code == 200
    body = res.json()
    assert body["allowed"] is True
    assert body["available_xp"] == 100

    # 구매 후: 보유 반영 + 가용 XP 차감, 레벨 산정용 누적 XP 는 불변
    listing = (await client.get("/api/themes")).json()
    ocean = next(i for i in listing["items"] if i["key"] == "ocean")
    assert ocean["allowed"] is True
    assert listing["available_xp"] == 100
    stats = (await client.get("/api/study/stats")).json()
    assert stats["xp"] == 600  # 레벨은 누적 기준 — 구매로 안 내려간다

    # 중복 구매 — 409
    assert (await client.post("/api/themes/ocean/purchase")).status_code == 409


async def test_purchase_rejected_when_insufficient_or_not_for_sale(client, db_session):
    from app.models import ThemeSetting

    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=10)  # 100 XP

    # 가격 미설정(미판매) — 422
    res = await client.post("/api/themes/candy/purchase")
    assert res.status_code == 422 and res.json()["detail"] == "theme_not_for_sale"

    # 잔액 부족 — 422 (가격은 DB 직접 설정 — admin API 경로는 다른 테스트가 커버)
    db_session.add(ThemeSetting(theme_key="candy", access="restricted", price_xp=500))
    await db_session.commit()
    res = await client.post("/api/themes/candy/purchase")
    assert res.status_code == 422 and res.json()["detail"] == "insufficient_xp"

    # free 테마는 구매 대상 아님
    assert (await client.post("/api/themes/note/purchase")).status_code == 422


async def test_reward_and_price_coexist(admin_client, client, db_session):
    """업적 보상과 XP 판매는 독립 설정 — 동시 사용 가능 (2026-08-05 결정).

    같은 테마를 업적으로도 얻고 XP 로도 살 수 있다. 보상 전용은 가격을
    비워두면 되고, 기간 한정 이벤트 판매는 후속(theme-mall.md P2).
    """
    db_session.add(ThemeRewardRule(achievement_key="first_game", theme_key="cat"))
    await db_session.commit()

    # 보상 규칙이 있어도 가격 설정 가능
    res = await admin_client.patch("/api/admin/themes/cat/price", json={"price_xp": 300})
    assert res.status_code == 200 and res.json()["price_xp"] == 300

    user = await login(client, db_session)
    await _earn_xp(db_session, user.id, reviews=100)  # 1000 XP

    # 카탈로그 — 해금 문구와 가격이 동시 노출
    listing = (await client.get("/api/themes")).json()
    cat = next(i for i in listing["items"] if i["key"] == "cat")
    assert cat["price_xp"] == 300
    assert cat["unlock"] is not None

    # 업적 미달성이어도 XP 로 구매 가능
    res = await client.post("/api/themes/cat/purchase")
    assert res.status_code == 200 and res.json()["allowed"] is True
