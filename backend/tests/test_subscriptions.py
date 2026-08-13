"""콘텐츠 담기(구독) 구조 — 같은 콘텐츠를 여러 사용자가 공유.

등록은 관리자 전용이고 사용자는 담기만 한다 (docs/specs/content-governance.md).
"""

from sqlalchemy import func, select

from app.models import Content, ContentSubscription, LearningItem
from tests.test_content_governance import PERMISSION
from tests.test_my_contents import login_as
from tests.test_study import seed_items

YT = "https://youtu.be/dQw4w9WgXcQ"


async def make_public_content(db, title="공용 영상", status="ready"):
    content = Content(
        source="youtube",
        youtube_video_id="dQw4w9WgXcQ",
        title=title,
        visibility="public",
        status=status,
    )
    db.add(content)
    await db.commit()
    return content


async def test_multiple_users_share_one_content_row(client, db_session):
    content = await make_public_content(db_session)

    user_a = await login_as(client, db_session, "a@example.com")
    assert (await client.post(f"/api/my/contents/{content.id}/subscribe")).status_code == 202
    user_b = await login_as(client, db_session, "b@example.com")
    assert (await client.post(f"/api/my/contents/{content.id}/subscribe")).status_code == 202

    count = (await db_session.execute(select(func.count(Content.id)))).scalar_one()
    assert count == 1  # 콘텐츠 테이블 중복 없음
    subs = (await db_session.execute(select(ContentSubscription.user_id))).scalars().all()
    assert sorted(subs) == sorted([user_a.id, user_b.id])
    assert (await client.get("/api/my/contents")).json()["total"] == 1


async def test_subscribe_is_idempotent(client, db_session):
    content = await make_public_content(db_session)
    await login_as(client, db_session, "a@example.com")
    await client.post(f"/api/my/contents/{content.id}/subscribe")
    await client.post(f"/api/my/contents/{content.id}/subscribe")
    subs = (await db_session.execute(select(func.count(ContentSubscription.id)))).scalar_one()
    assert subs == 1


async def test_cannot_subscribe_unready_or_private_content(client, db_session):
    await login_as(client, db_session, "a@example.com")
    pending = await make_public_content(db_session, title="준비중", status="pending")
    assert (await client.post(f"/api/my/contents/{pending.id}/subscribe")).status_code == 404

    private = Content(source="manual", title="개인", visibility="private", status="ready")
    db_session.add(private)
    await db_session.commit()
    assert (await client.post(f"/api/my/contents/{private.id}/subscribe")).status_code == 404


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


async def test_unsubscribe_keeps_public_content_for_other_subscribers(client, db_session):
    content = await make_public_content(db_session)
    await login_as(client, db_session, "a@example.com")
    await client.post(f"/api/my/contents/{content.id}/subscribe")
    await login_as(client, db_session, "b@example.com")
    await client.post(f"/api/my/contents/{content.id}/subscribe")

    # B 가 빼도 콘텐츠는 유지 (공용 + A 가 남아있음)
    assert (await client.delete(f"/api/my/contents/{content.id}")).status_code == 204
    assert await db_session.get(Content, content.id) is not None
    assert (await client.get("/api/my/contents")).json()["total"] == 0


async def test_last_unsubscribe_deletes_private_content(client, db_session):
    """개인 콘텐츠(신규 등록 차단 이전 잔존분)는 마지막 구독자가 떠나면 본체 삭제."""
    user = await login_as(client, db_session, "a@example.com")
    content = Content(source="manual", title="잔존 개인", visibility="private", status="ready")
    db_session.add(content)
    await db_session.flush()
    db_session.add(ContentSubscription(content_id=content.id, user_id=user.id))
    await db_session.commit()

    assert (await client.delete(f"/api/my/contents/{content.id}")).status_code == 204
    assert await db_session.get(Content, content.id) is None


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


async def test_resubscribe_restores_fsrs_state(client, db_session):
    """재담기 시 FSRS 상태(reps/state/due_at) 그대로 복원 — 빼기는 구독 행만 지운다는 실증."""
    from sqlalchemy import select as sa_select

    from app.models import ItemOccurrence, ReviewCard

    user = await login_as(client, db_session, "a@example.com")
    items = await seed_items(db_session, count=1)
    content_id = (
        await db_session.execute(
            sa_select(ItemOccurrence.content_id).where(ItemOccurrence.item_id == items[0].id)
        )
    ).scalar_one()

    # 학습 1회로 FSRS 상태를 만든다 (reps 1, due_at 미래로 스케줄)
    question = (await client.get("/api/study/queue")).json()["questions"][0]
    correct = items[0].ko_text if question["quiz_mode"] == "choice_en2ko" else items[0].en_text
    res = await client.post(
        "/api/study/answer",
        json={
            "card_id": question["card_id"],
            "quiz_mode": question["quiz_mode"],
            "answer": correct,
            "duration_ms": 3000,
        },
    )
    assert res.status_code == 200

    card = (
        await db_session.execute(sa_select(ReviewCard).where(ReviewCard.user_id == user.id))
    ).scalar_one()
    before = (card.reps, card.state, card.due_at)
    assert card.reps == 1

    # 빼기 → 재담기: 카드 행이 삭제·초기화 없이 해제 전 상태 그대로
    assert (await client.delete(f"/api/my/contents/{content_id}")).status_code == 204
    assert (await client.post(f"/api/my/contents/{content_id}/subscribe")).status_code == 202
    await db_session.refresh(card)
    assert (card.reps, card.state, card.due_at) == before

    from app.services.visibility import visible_item_clause

    visible = (
        (await db_session.execute(sa_select(LearningItem.id).where(visible_item_clause(user.id))))
        .scalars()
        .all()
    )
    assert items[0].id in visible


async def test_stats_levels_exclude_unsubscribed_cards(client, db_session):
    """컬렉션(레벨) 분자도 가시성 규칙 — 빼면 카드 수·분모가 함께 빠진다."""
    from app.models import ItemOccurrence, ReviewCard

    await login_as(client, db_session, "a@example.com")
    items = await seed_items(db_session, count=1)
    content_id = (
        await db_session.execute(
            select(ItemOccurrence.content_id).where(ItemOccurrence.item_id == items[0].id)
        )
    ).scalar_one()
    assert (await client.post("/api/cards", json={"item_id": items[0].id})).status_code == 200
    # 컬렉션 분자는 '한 번이라도 푼 카드' — 담기만 한 카드는 안 세므로 학습 이력을 만든다
    card = (
        await db_session.execute(select(ReviewCard).where(ReviewCard.item_id == items[0].id))
    ).scalar_one()
    card.reps = 1
    await db_session.commit()

    def word_level(stats):
        return next(lv for lv in stats["levels"] if lv["item_type"] == "word")

    before = word_level((await client.get("/api/study/stats")).json())
    assert before["cards"] == 1 and before["available_items"] == 1

    assert (await client.delete(f"/api/my/contents/{content_id}")).status_code == 204
    after = word_level((await client.get("/api/study/stats")).json())
    assert after["cards"] == 0 and after["available_items"] == 0


async def test_unsubscribed_words_leave_default_game_pool(wired_db):
    """구독 해제한 콘텐츠의 학습 단어는 게임 기본 풀(테트리스·퀴즈 로얄)에서도 빠진다."""
    from datetime import UTC, datetime

    from app.models import ItemOccurrence, ReviewCard, User
    from app.services.game.manager import load_word_pool

    user = User(google_sub="g-a", email="a@x.com", name="A")
    wired_db.add(user)
    await wired_db.flush()
    content = Content(source="manual", title="소재", status="ready", visibility="public")
    wired_db.add(content)
    await wired_db.flush()
    sub = ContentSubscription(content_id=content.id, user_id=user.id)
    wired_db.add(sub)
    for i in range(3):
        item = LearningItem(
            item_type="word",
            en_text=f"poolword{i}",
            ko_text=f"뜻{i}",
            normalized_key=f"poolword{i}",
            review_status="approved",
        )
        wired_db.add(item)
        await wired_db.flush()
        wired_db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
        wired_db.add(
            ReviewCard(user_id=user.id, item_id=item.id, state="new", due_at=datetime.now(UTC))
        )
    await wired_db.commit()

    assert len(await load_word_pool(user.id)) == 3

    await wired_db.delete(sub)
    await wired_db.commit()
    assert await load_word_pool(user.id) == []


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

    # 라이선스 미확인 승격은 허락 증빙 필요 (content-governance.md)
    res = await admin_client.post(
        "/api/admin/contents",
        json={"source": "youtube", "url": YT, "permission": PERMISSION},
    )
    assert res.status_code == 202
    assert res.json()["promoted"] is True
    await db_session.refresh(content)
    assert content.visibility == "public"


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


async def test_game_pool_public_content_excludes_unapproved(wired_db):
    """콘텐츠 선택 대전 풀 — 공용은 approved 만, 개인은 rejected 만 제외
    (visible_item_clause 와 동일 규칙, content-governance.md)."""
    from app.models import ItemOccurrence, User
    from app.services.game.manager import load_word_pool_from_contents

    u = User(google_sub="g-p", email="p@x.com", name="P")
    wired_db.add(u)
    await wired_db.flush()

    content = Content(
        source="manual", title="공용 소재", status="ready", visibility="public", created_by=u.id
    )
    wired_db.add(content)
    await wired_db.flush()
    wired_db.add(ContentSubscription(content_id=content.id, user_id=u.id))
    for i, status_ in enumerate(["approved"] * 12 + ["pending", "rejected"]):
        item = LearningItem(
            item_type="word",
            en_text=f"pubw{i}",
            ko_text=f"공뜻{i}",
            normalized_key=f"pubw{i}",
            review_status=status_,
        )
        wired_db.add(item)
        await wired_db.flush()
        wired_db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
    await wired_db.commit()

    pool = await load_word_pool_from_contents(u.id, [content.id])
    assert len(pool) == 12  # pending·rejected 제외
    pool_words = {en for _, en, _ in pool}
    assert "pubw12" not in pool_words  # pending
    assert "pubw13" not in pool_words  # rejected


async def test_private_promotion_preserves_subscriber_visibility(client, db_session):
    """개인→공용 일괄 승격 시맨틱 (마이그레이션 a6b7c8d9e0f1 과 동일 SQL) —
    pending 항목을 먼저 승인해야 기존 구독자의 학습 재료가 사라지지 않는다."""
    from sqlalchemy import text

    from app.services.visibility import visible_item_clause

    user = await login_as(client, db_session, "a@example.com")
    items = await seed_items(
        db_session, count=2, status="pending", visibility="private", owner=user.id
    )

    def visible_count():
        return db_session.execute(
            select(func.count(LearningItem.id)).where(
                LearningItem.id.in_([i.id for i in items]), visible_item_clause(user.id)
            )
        )

    # 승격 전: 개인 콘텐츠라 pending 도 보인다
    assert (await visible_count()).scalar_one() == 2

    # 마이그레이션과 동일한 2단계 SQL (순서 뒤집으면 공용+pending 이 되어 소실)
    await db_session.execute(
        text(
            "UPDATE learning_items SET review_status = 'approved' "
            "WHERE review_status = 'pending' AND id IN ("
            "  SELECT item_id FROM item_occurrences WHERE content_id IN ("
            "    SELECT id FROM contents WHERE visibility = 'private'))"
        )
    )
    await db_session.execute(
        text("UPDATE contents SET visibility = 'public' WHERE visibility = 'private'")
    )
    await db_session.commit()

    # 승격 후: 공용 승인 항목으로 계속 보이고, 담김(구독)도 그대로
    assert (await visible_count()).scalar_one() == 2
    subs = (
        await db_session.execute(
            select(func.count(ContentSubscription.id)).where(ContentSubscription.user_id == user.id)
        )
    ).scalar_one()
    assert subs >= 1
