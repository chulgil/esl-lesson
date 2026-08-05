"""담기/빼기와 무관한 단어 단일성 — 같은 단어는 카드 1장, 중복 도입 금지.

2026-08-05 사용자 확인 요청: 영상 담기/빼기를 반복해도 기존에 학습한 단어가
학습 리스트에 중복으로 나타나면 안 된다. 파이프라인의 전역 upsert
(item_type+normalized_key, pipeline.py _upsert_item) + 카드 유일 제약
(uq_cards_user_item) + 가시성 규칙이 이 불변식을 보장한다 — 회귀로 고정.
"""

from sqlalchemy import delete, func, select

from app.models import Content, ContentSubscription, ItemOccurrence, ReviewCard
from tests.test_study import login, seed_items


async def test_same_word_across_contents_keeps_single_card(client, db_session):
    user = await login(client, db_session)
    items = await seed_items(db_session, count=1)  # 콘텐츠 A + 항목
    item = items[0]
    content_a_id = (
        await db_session.execute(
            select(ItemOccurrence.content_id).where(ItemOccurrence.item_id == item.id)
        )
    ).scalar_one()

    # 같은 항목이 콘텐츠 B 에도 등장 (파이프라인 전역 upsert 재현)
    content_b = Content(source="manual", title="B", status="ready", visibility="public")
    db_session.add(content_b)
    await db_session.flush()
    db_session.add(ContentSubscription(content_id=content_b.id, user_id=user.id))
    db_session.add(ItemOccurrence(item_id=item.id, content_id=content_b.id))
    await db_session.commit()

    # 첫 큐 — 신규 카드 도입 (1장)
    res = (await client.get("/api/study/queue")).json()
    assert [q["item_id"] for q in res["questions"]].count(item.id) == 1

    # 콘텐츠 A 를 뺐다가(구독 해제) 다시 큐 조회 — B 로 여전히 가시,
    # 이미 카드가 있으므로 신규로 재도입되지 않는다
    await db_session.execute(
        delete(ContentSubscription).where(
            ContentSubscription.content_id == content_a_id,
            ContentSubscription.user_id == user.id,
        )
    )
    await db_session.commit()
    res = (await client.get("/api/study/queue")).json()
    assert [q["item_id"] for q in res["questions"]].count(item.id) <= 1

    # 불변식: 이 단어의 카드는 정확히 1장 (중복 도입 없음)
    card_count = (
        await db_session.execute(
            select(func.count(ReviewCard.id)).where(
                ReviewCard.user_id == user.id, ReviewCard.item_id == item.id
            )
        )
    ).scalar_one()
    assert card_count == 1
