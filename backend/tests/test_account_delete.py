"""회원탈퇴(DELETE /api/me) — 개인정보 즉시 파기 + 운영 시크릿 가드."""

import pytest
from sqlalchemy import func, select

from app.core.config import Settings, assert_production_secrets
from app.models import Content, ReviewCard, User, UserSettings
from tests.test_study import login, seed_items


async def test_delete_me_removes_user_and_data(client, db_session):
    """탈퇴 시 유저·설정·카드가 삭제되고 세션이 무효화된다."""
    user = await login(client, db_session)
    items = await seed_items(db_session, count=1)
    await client.post("/api/cards", json={"item_id": items[0].id})

    res = await client.delete("/api/me")
    assert res.status_code == 204

    assert (await db_session.get(User, user.id)) is None
    assert (await db_session.get(UserSettings, user.id)) is None
    cards = (
        await db_session.execute(
            select(func.count(ReviewCard.id)).where(ReviewCard.user_id == user.id)
        )
    ).scalar_one()
    assert cards == 0

    # 쿠키 삭제 → 재요청은 401
    again = await client.get("/api/me")
    assert again.status_code == 401


async def test_delete_me_cleans_orphan_private_content(client, db_session):
    """내가 마지막 구독자인 개인 콘텐츠는 본체 삭제, 공용 콘텐츠는 유지."""
    user = await login(client, db_session)
    private_items = await seed_items(db_session, count=1, visibility="private", owner=user.id)
    public_items = await seed_items(db_session, count=1)

    res = await client.delete("/api/me")
    assert res.status_code == 204

    private_contents = (
        await db_session.execute(
            select(func.count(Content.id)).where(Content.visibility == "private")
        )
    ).scalar_one()
    assert private_contents == 0
    public_contents = (
        await db_session.execute(
            select(func.count(Content.id)).where(Content.visibility == "public")
        )
    ).scalar_one()
    assert public_contents == 1
    assert private_items and public_items  # 픽스처 사용 명시


def test_assert_production_secrets_blocks_unset_jwt():
    """운영 신호(cookie_secure)에서 JWT 시크릿 미설정이면 기동 실패."""
    with pytest.raises(RuntimeError):
        assert_production_secrets(Settings(jwt_secret="", cookie_secure=True))

    # 로컬(cookie_secure=false)이나 운영+실시크릿은 통과
    assert_production_secrets(Settings(jwt_secret="", cookie_secure=False))
    assert_production_secrets(Settings(jwt_secret="prod-ok", cookie_secure=True))
