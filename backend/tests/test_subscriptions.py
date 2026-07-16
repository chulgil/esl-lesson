"""콘텐츠 구독 구조: 동일 영상 공유·즉시 재사용 (2026-07-11 요구사항)."""

from sqlalchemy import func, select

from app.models import Content, ContentSubscription, LearningItem
from tests.test_my_contents import login_as
from tests.test_study import seed_items

YT = "https://youtu.be/dQw4w9WgXcQ"


async def test_same_video_reuses_content_and_subscribes(client, db_session):
    user_a = await login_as(client, db_session, "a@example.com")
    first = await client.post("/api/my/contents", json={"source": "youtube", "url": YT})
    assert first.status_code == 202
    content_id = first.json()["id"]
    assert first.json()["reused"] is False

    # 다른 사용자가 같은 영상 등록 -> 콘텐츠 재사용 + 구독 추가 (재추출 없음)
    user_b = await login_as(client, db_session, "b@example.com")
    second = await client.post("/api/my/contents", json={"source": "youtube", "url": YT})
    assert second.status_code == 202
    assert second.json() == {"id": content_id, "status": "pending", "reused": True}

    count = (await db_session.execute(select(func.count(Content.id)))).scalar_one()
    assert count == 1  # 콘텐츠 테이블 중복 없음
    subs = (await db_session.execute(select(ContentSubscription.user_id))).scalars().all()
    assert sorted(subs) == sorted([user_a.id, user_b.id])

    # 양쪽 다 내 콘텐츠 목록에 보인다
    assert (await client.get("/api/my/contents")).json()["total"] == 1


async def test_resubscribe_is_idempotent_and_free_of_limit(client, db_session):
    await login_as(client, db_session, "a@example.com")
    await client.post("/api/my/contents", json={"source": "youtube", "url": YT})
    again = await client.post("/api/my/contents", json={"source": "youtube", "url": YT})
    assert again.json()["reused"] is True
    subs = (await db_session.execute(select(func.count(ContentSubscription.id)))).scalar_one()
    assert subs == 1


async def test_subscriber_sees_shared_private_items_in_queue(client, db_session):
    owner = await login_as(client, db_session, "a@example.com")
    items = await seed_items(
        db_session, count=3, status="pending", visibility="private", owner=owner.id
    )
    content_id = (
        await db_session.execute(select(Content.id).where(Content.visibility == "private"))
    ).scalar_one()

    # B가 같은 콘텐츠를 구독하면 즉시 같은 항목으로 학습 가능
    user_b = await login_as(client, db_session, "b@example.com")
    db_session.add(ContentSubscription(content_id=content_id, user_id=user_b.id))
    await db_session.commit()

    queue = (await client.get("/api/study/queue")).json()
    assert len(queue["questions"]) == len(items)


async def test_unsubscribe_keeps_content_for_other_subscribers(client, db_session):
    await login_as(client, db_session, "a@example.com")
    res = await client.post("/api/my/contents", json={"source": "youtube", "url": YT})
    content_id = res.json()["id"]
    await login_as(client, db_session, "b@example.com")
    await client.post("/api/my/contents", json={"source": "youtube", "url": YT})

    # B 구독 해지 -> 콘텐츠는 유지 (A가 남아있음)
    assert (await client.delete(f"/api/my/contents/{content_id}")).status_code == 204
    assert await db_session.get(Content, content_id) is not None
    assert (await client.get("/api/my/contents")).json()["total"] == 0


async def test_last_unsubscribe_deletes_private_content(client, db_session):
    await login_as(client, db_session, "a@example.com")
    res = await client.post("/api/my/contents", json={"source": "youtube", "url": YT})
    content_id = res.json()["id"]
    assert (await client.delete(f"/api/my/contents/{content_id}")).status_code == 204
    assert await db_session.get(Content, content_id) is None


async def test_delete_preserves_practice_records(client, db_session):
    """삭제 기획: 향후 학습 목록에서만 빠지고, 연습한 기록(카드·로그)은 남는다.

    목표 — 관심 콘텐츠로 학습하되, 콘텐츠를 정리해도 그간의 실력 기록은 유지.
    """
    from datetime import UTC, datetime

    from app.models import ItemOccurrence, ReviewCard, ReviewLog
    from app.services.visibility import visible_item_clause

    user = await login_as(client, db_session, "a@example.com")
    items = await seed_items(db_session, count=2, visibility="private", owner=user.id)
    content_id = (
        await db_session.execute(
            select(ItemOccurrence.content_id).where(ItemOccurrence.item_id == items[0].id)
        )
    ).scalar_one()

    # 첫 항목만 연습 이력 존재
    now = datetime.now(UTC)
    card = ReviewCard(user_id=user.id, item_id=items[0].id, due_at=now)
    db_session.add(card)
    await db_session.flush()
    db_session.add(
        ReviewLog(
            card_id=card.id,
            user_id=user.id,
            rating=3,
            correct=True,
            quiz_mode="meaning",
            state_before="new",
            reviewed_at=now,
        )
    )
    await db_session.commit()

    assert (await client.delete(f"/api/my/contents/{content_id}")).status_code == 204

    # 콘텐츠는 삭제, 연습 기록이 있는 항목·카드·로그는 보존
    assert await db_session.get(Content, content_id) is None
    assert await db_session.get(LearningItem, items[0].id) is not None
    assert await db_session.get(LearningItem, items[1].id) is None  # 기록 없는 고아만 정리
    assert await db_session.get(ReviewCard, card.id) is not None
    logs = (await db_session.execute(select(func.count(ReviewLog.id)))).scalar_one()
    assert logs == 1

    # 출처가 사라진 항목은 가시성 규칙에 따라 향후 학습 목록에서 제외
    visible = (
        (await db_session.execute(select(LearningItem.id).where(visible_item_clause(user.id))))
        .scalars()
        .all()
    )
    assert items[0].id not in visible


async def test_admin_registering_existing_private_promotes_to_public(admin_client, db_session):
    # 일반 사용자가 먼저 등록한 영상
    content = Content(
        source="youtube",
        youtube_video_id="dQw4w9WgXcQ",
        title="개인 영상",
        visibility="private",
        status="ready",
    )
    db_session.add(content)
    await db_session.commit()

    # CC 게이트 도입(2026-07-14) — 라이선스 미확인 승격은 관리자 오버라이드 필요
    res = await admin_client.post(
        "/api/admin/contents",
        json={"source": "youtube", "url": YT, "allow_non_cc": True},
    )
    assert res.status_code == 202
    assert res.json()["promoted"] is True
    await db_session.refresh(content)
    assert content.visibility == "public"


async def test_daily_limit_counts_only_new_creations(client, db_session):
    """기존 콘텐츠 구독은 한도를 소모하지 않는다."""
    from datetime import UTC, datetime

    user = await login_as(client, db_session, "a@example.com")
    for i in range(10):
        db_session.add(
            Content(
                source="manual",
                title=f"c{i}",
                visibility="private",
                created_by=user.id,
                created_at=datetime.now(UTC),
            )
        )
    other = Content(
        source="youtube",
        youtube_video_id="dQw4w9WgXcQ",
        title="남의 영상",
        visibility="private",
        status="ready",
    )
    db_session.add(other)
    await db_session.commit()

    # 신규 생성은 429
    blocked = await client.post(
        "/api/my/contents", json={"source": "manual", "title": "x", "script_en": "Hi."}
    )
    assert blocked.status_code == 429
    # 기존 영상 구독은 허용
    reused = await client.post("/api/my/contents", json={"source": "youtube", "url": YT})
    assert reused.status_code == 202
    assert reused.json()["reused"] is True


@__import__("pytest").fixture
async def wired_db(db_session, monkeypatch):
    import app.core.db as core_db

    class FakeFactory:
        def __call__(self):
            return FakeSessionCtx()

    class FakeSessionCtx:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(core_db, "_engine", object())
    monkeypatch.setattr(core_db, "_session_factory", FakeFactory())
    return db_session


async def test_game_pool_allows_subscribed_content(wired_db):
    import pytest

    from app.models import ItemOccurrence, User
    from app.services.game.manager import WordPoolError, load_word_pool_from_contents

    a = User(google_sub="g-a", email="a@x.com", name="A")
    b = User(google_sub="g-b", email="b@x.com", name="B")
    wired_db.add_all([a, b])
    await wired_db.flush()

    content = Content(
        source="manual", title="소재", status="ready", visibility="private", created_by=a.id
    )
    wired_db.add(content)
    await wired_db.flush()
    wired_db.add(ContentSubscription(content_id=content.id, user_id=a.id))
    for i in range(12):
        item = LearningItem(
            item_type="word",
            en_text=f"gamew{i}",
            ko_text=f"뜻{i}",
            normalized_key=f"gamew{i}",
            review_status="pending",
        )
        wired_db.add(item)
        await wired_db.flush()
        wired_db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
    await wired_db.commit()

    # 구독자 B는 사용 가능
    wired_db.add(ContentSubscription(content_id=content.id, user_id=b.id))
    await wired_db.commit()
    pool = await load_word_pool_from_contents(b.id, [content.id])
    assert len(pool) == 12

    # 미구독 사용자는 거부
    c = User(google_sub="g-c", email="c@x.com", name="C")
    wired_db.add(c)
    await wired_db.commit()
    with pytest.raises(WordPoolError):
        await load_word_pool_from_contents(c.id, [content.id])
