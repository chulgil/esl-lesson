"""내 콘텐츠 + 가시성 격리 (docs/specs/content-governance.md)."""

from sqlalchemy import select

from app.api.auth import upsert_google_user
from app.core.config import get_settings
from app.core.security import SESSION_COOKIE, create_session_token
from app.models import Content, LearningItem, ReviewCard
from tests.test_study import seed_items, subscribe_existing_public


async def login_as(client, db, email):
    user = await upsert_google_user(
        db,
        {"sub": f"g-{email}", "email": email, "email_verified": True, "name": email},
        get_settings(),
    )
    client.cookies.set(SESSION_COOKIE, create_session_token(user))
    await subscribe_existing_public(db, user.id)
    return user


async def test_user_cannot_register_content(client, db_session):
    """등록은 관리자 전용 — 유튜브·수기 두 경로 모두 사용자에게 닫혀 있다."""
    await login_as(client, db_session, "u1@example.com")
    youtube = await client.post(
        "/api/my/contents", json={"source": "youtube", "url": "https://youtu.be/dQw4w9WgXcQ"}
    )
    manual = await client.post(
        "/api/my/contents",
        json={"source": "manual", "title": "내 노트", "script_en": "Hello there."},
    )
    assert youtube.status_code == 405
    assert manual.status_code == 405
    assert (await db_session.execute(select(Content.id))).scalars().all() == []


async def test_private_items_visible_only_to_owner(client, db_session):
    owner = await login_as(client, db_session, "owner@example.com")
    # 개인 콘텐츠 항목: pending 이어도 소유자에게 자동 편입 (rule b)
    await seed_items(db_session, count=4, status="pending", visibility="private", owner=owner.id)

    queue = (await client.get("/api/study/queue")).json()
    assert len(queue["questions"]) == 4

    # 다른 사용자에게는 보이지 않는다
    await login_as(client, db_session, "stranger@example.com")
    queue2 = (await client.get("/api/study/queue")).json()
    assert queue2["questions"] == []


async def test_public_pending_items_hidden_until_approved(client, db_session):
    await login_as(client, db_session, "u1@example.com")
    await seed_items(db_session, count=3, status="pending", visibility="public")
    queue = (await client.get("/api/study/queue")).json()
    assert queue["questions"] == []  # 공용은 관리자 승인 전 노출 금지


async def test_library_shows_public_and_mine_only(client, db_session):
    owner = await login_as(client, db_session, "owner@example.com")
    await seed_items(db_session, count=1, visibility="public")
    await seed_items(db_session, count=1, visibility="private", owner=owner.id)
    stranger = await upsert_google_user(
        db_session,
        {"sub": "g-x", "email": "x@example.com", "email_verified": True, "name": "X"},
        get_settings(),
    )
    await seed_items(db_session, count=1, visibility="private", owner=stranger.id)

    listed = (await client.get("/api/contents")).json()
    assert listed["total"] == 2  # 공용 1 + 내 것 1 (남의 개인 콘텐츠 제외)
    assert sorted(i["mine"] for i in listed["items"]) == [False, True]


async def test_admin_list_excludes_private_contents(admin_client, db_session):
    admin_user = (
        (await db_session.execute(select(__import__("app.models", fromlist=["User"]).User)))
        .scalars()
        .first()
    )
    await seed_items(db_session, count=1, visibility="private", owner=admin_user.id)
    await seed_items(db_session, count=1, visibility="public")

    listed = (await admin_client.get("/api/admin/contents")).json()
    assert all(c["visibility"] == "public" for c in listed["items"])


async def test_exclude_item_suspends_card(client, db_session):
    owner = await login_as(client, db_session, "owner@example.com")
    items = await seed_items(
        db_session, count=1, status="pending", visibility="private", owner=owner.id
    )
    res = await client.post(f"/api/my/items/{items[0].id}/exclude")
    assert res.status_code == 200
    card = (
        await db_session.execute(
            select(ReviewCard).where(
                ReviewCard.user_id == owner.id, ReviewCard.item_id == items[0].id
            )
        )
    ).scalar_one()
    assert card.suspended is True

    # 제외된 항목은 큐에 안 나온다
    queue = (await client.get("/api/study/queue")).json()
    assert queue["questions"] == []

    # 복귀
    await client.post(f"/api/my/items/{items[0].id}/include")
    queue = (await client.get("/api/study/queue")).json()
    assert len(queue["questions"]) == 1


async def test_cannot_exclude_others_item(client, db_session):
    stranger = await upsert_google_user(
        db_session,
        {"sub": "g-x", "email": "x@example.com", "email_verified": True, "name": "X"},
        get_settings(),
    )
    items = await seed_items(
        db_session, count=1, status="pending", visibility="private", owner=stranger.id
    )
    await login_as(client, db_session, "me@example.com")
    res = await client.post(f"/api/my/items/{items[0].id}/exclude")
    assert res.status_code == 403


async def test_others_private_content_detail_forbidden(client, db_session):
    stranger = await upsert_google_user(
        db_session,
        {"sub": "g-x", "email": "x@example.com", "email_verified": True, "name": "X"},
        get_settings(),
    )
    await seed_items(db_session, count=1, visibility="private", owner=stranger.id)
    content_id = (
        await db_session.execute(select(Content.id).where(Content.visibility == "private"))
    ).scalar_one()

    await login_as(client, db_session, "me@example.com")
    assert (await client.get(f"/api/my/contents/{content_id}")).status_code == 404
    assert (await client.get(f"/api/contents/{content_id}")).status_code == 404


async def test_distractor_pool_excludes_others_private(client, db_session):
    """오답 보기에 남의 개인 항목이 새지 않는다."""
    stranger = await upsert_google_user(
        db_session,
        {"sub": "g-x", "email": "x@example.com", "email_verified": True, "name": "X"},
        get_settings(),
    )
    await seed_items(
        db_session, count=10, status="pending", visibility="private", owner=stranger.id
    )
    me = await login_as(client, db_session, "me@example.com")
    await seed_items(db_session, count=1, status="pending", visibility="private", owner=me.id)

    queue = (await client.get("/api/study/queue")).json()
    assert len(queue["questions"]) == 1
    q = queue["questions"][0]
    my_item = await db_session.get(LearningItem, q["item_id"])
    answer = my_item.ko_text if q["quiz_mode"] == "choice_en2ko" else my_item.en_text
    stranger_texts = {f"uniqueprivate{i}" for i in range(10)}
    for choice in q["choices"]:
        if choice == answer:
            continue
        assert choice not in stranger_texts  # 남의 개인 단어가 보기로 등장하면 안 됨
