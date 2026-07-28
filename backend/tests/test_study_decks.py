"""덱(=담은 콘텐츠) 카운트 + 덱 한정 학습 큐 (docs/specs/study-decks.md)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import (
    Content,
    ContentSubscription,
    ItemOccurrence,
    LearningItem,
    ReviewCard,
    User,
)
from tests.test_study import login


async def seed_deck(db, user_id, title, count, visibility="public"):
    """덱 1개 = 콘텐츠 + 구독 + 항목 N개. 제목을 지정해 덱 정렬/표기를 검증한다."""
    content = Content(source="manual", title=title, status="ready", visibility=visibility)
    db.add(content)
    await db.flush()
    db.add(ContentSubscription(content_id=content.id, user_id=user_id))
    items = []
    for i in range(count):
        item = LearningItem(
            item_type="word",
            en_text=f"{title}w{i}",
            ko_text=f"뜻{title}{i}",
            normalized_key=f"{title}w{i}",
            review_status="approved",
        )
        db.add(item)
        await db.flush()
        db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
        items.append(item)
    await db.commit()
    return content, items


async def test_decks_lists_subscribed_contents_with_counts(client, db_session):
    """구독 콘텐츠만 노출, due/new/total 은 해당 콘텐츠 등장 항목만 집계."""
    me = await login(client, db_session)
    deck_a, items_a = await seed_deck(db_session, me.id, "aaa영상", 3)
    deck_b, _items_b = await seed_deck(db_session, me.id, "bbb영상", 2)

    # 타인 전용 콘텐츠 — 내 덱 목록에 나오면 안 된다
    other = User(google_sub="g-deck-other", email="do@example.com", name="남", nickname="남")
    db_session.add(other)
    await db_session.flush()
    await seed_deck(db_session, other.id, "남의영상", 1, visibility="private")

    now = datetime.now(UTC)
    db_session.add_all(
        [
            # due 1개 (미suspend·만기)
            ReviewCard(
                user_id=me.id, item_id=items_a[0].id, state="review", due_at=now - timedelta(days=1)
            ),
            # suspended — due 제외, total 포함
            ReviewCard(
                user_id=me.id,
                item_id=items_a[1].id,
                state="review",
                due_at=now - timedelta(days=1),
                suspended=True,
            ),
        ]
    )
    await db_session.commit()

    res = await client.get("/api/study/decks")
    assert res.status_code == 200
    decks = res.json()["items"]
    assert [d["content_id"] for d in decks] == [deck_a.id, deck_b.id]  # due DESC → title
    a, b = decks
    assert a == {
        "content_id": deck_a.id,
        "title": "aaa영상",
        "due": 1,
        "new_available": 1,  # items_a[2] 만 카드 없음
        "total_cards": 2,
    }
    assert b["due"] == 0 and b["new_available"] == 2 and b["total_cards"] == 0


async def test_deck_shared_item_counts_in_both_decks(client, db_session):
    """같은 항목이 두 콘텐츠에 등장하면 due 는 양쪽 덱에 모두 집계 (다대다 — Anki 와 다른 점)."""
    me = await login(client, db_session)
    deck_a, items_a = await seed_deck(db_session, me.id, "겹침a", 1)
    deck_b, _ = await seed_deck(db_session, me.id, "겹침b", 1)
    db_session.add(ItemOccurrence(item_id=items_a[0].id, content_id=deck_b.id))
    db_session.add(
        ReviewCard(
            user_id=me.id,
            item_id=items_a[0].id,
            state="review",
            due_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.commit()

    decks = {d["content_id"]: d for d in (await client.get("/api/study/decks")).json()["items"]}
    assert decks[deck_a.id]["due"] == 1
    assert decks[deck_b.id]["due"] == 1


async def test_deck_disappears_after_unsubscribe(client, db_session):
    me = await login(client, db_session)
    deck_a, _ = await seed_deck(db_session, me.id, "해지영상", 1)
    assert len((await client.get("/api/study/decks")).json()["items"]) == 1

    res = await client.delete(f"/api/my/contents/{deck_a.id}")
    assert res.status_code == 204
    assert (await client.get("/api/study/decks")).json()["items"] == []


async def test_queue_scoped_to_content(client, db_session):
    """content_id 지정 시 due·신규 도입 모두 해당 콘텐츠 등장 항목으로 한정."""
    me = await login(client, db_session)
    deck_a, items_a = await seed_deck(db_session, me.id, "큐a", 3)
    _deck_b, items_b = await seed_deck(db_session, me.id, "큐b", 2)
    # 다른 덱(B)의 due 카드 — A 한정 큐에 나오면 안 된다
    db_session.add(
        ReviewCard(
            user_id=me.id,
            item_id=items_b[0].id,
            state="review",
            due_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db_session.commit()

    res = await client.get(f"/api/study/queue?content_id={deck_a.id}")
    assert res.status_code == 200
    body = res.json()
    assert body["deck"] == {"content_id": deck_a.id, "title": "큐a"}
    ids_a = {i.id for i in items_a}
    assert len(body["questions"]) == 3
    assert all(q["item_id"] in ids_a for q in body["questions"])

    # 신규 카드도 A 항목만 생성됐다 (B 는 due 카드 1개뿐)
    cards = (
        (await db_session.execute(select(ReviewCard.item_id).where(ReviewCard.user_id == me.id)))
        .scalars()
        .all()
    )
    assert set(cards) == ids_a | {items_b[0].id}

    # 전체 큐(미지정)는 기존 그대로 — deck 없음 + B due 포함
    full = (await client.get("/api/study/queue")).json()
    assert full["deck"] is None
    assert {q["item_id"] for q in full["questions"]} >= {items_b[0].id}


async def test_queue_unsubscribed_content_404(client, db_session):
    """구독 안 한 콘텐츠·없는 콘텐츠는 404 (존재 여부 비노출)."""
    me = await login(client, db_session)
    other = User(google_sub="g-deck-404", email="d404@example.com", name="남", nickname="남")
    db_session.add(other)
    await db_session.flush()
    theirs, _ = await seed_deck(db_session, other.id, "남의큐", 1, visibility="private")

    assert (await client.get(f"/api/study/queue?content_id={theirs.id}")).status_code == 404
    assert (await client.get("/api/study/queue?content_id=999999")).status_code == 404
    assert me.id  # 로그인 자체는 유효 — 404 가 인증 문제로 인한 것이 아님을 보장
