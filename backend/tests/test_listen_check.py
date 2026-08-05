"""재청취 이해도 셀프 체크 — 1단계(첫 청취) vs 6단계(루틴 후) 전후 비교.

기획: docs/proposal/effectiveness-audit-2026-08.md P1 — "안 들리던 게 들린다"를
측정 가능한 증거로.
"""

from sqlalchemy import select

from app.models import Content, ContentSubscription
from tests.test_study import login, seed_items


async def _subscribed_content_id(db, user_id: int) -> int:
    """seed_items 가 만든 구독 콘텐츠 id."""
    return (
        await db.execute(
            select(ContentSubscription.content_id)
            .where(ContentSubscription.user_id == user_id)
            .limit(1)
        )
    ).scalar_one()


async def test_listen_check_requires_subscription(client, db_session):
    await login(client, db_session)
    content = Content(source="manual", title="남의 것", status="ready", visibility="public")
    db_session.add(content)
    await db_session.commit()
    # 비구독 — 존재 여부도 흘리지 않는 404 (my_contents 계약)
    res = await client.post(
        f"/api/contents/{content.id}/listen-check", json={"stage": 1, "score": 3}
    )
    assert res.status_code == 404
    assert (
        await client.post("/api/contents/999999/listen-check", json={"stage": 1, "score": 3})
    ).status_code == 404


async def test_listen_check_records_and_updates(client, db_session):
    user = await login(client, db_session)
    await seed_items(db_session, count=1)
    cid = await _subscribed_content_id(db_session, user.id)

    res = await client.post(f"/api/contents/{cid}/listen-check", json={"stage": 1, "score": 2})
    assert res.status_code == 200
    assert res.json() == {"stage": 1, "score": 2}

    # 같은 stage 재제출 — 새 행이 아니라 갱신 (upsert)
    res = await client.post(f"/api/contents/{cid}/listen-check", json={"stage": 1, "score": 4})
    assert res.status_code == 200
    assert res.json()["score"] == 4
    assert (await client.get(f"/api/contents/{cid}/routine")).json()["listen"]["before"] == 4

    # 범위 밖 — 422
    for bad in ({"stage": 1, "score": 0}, {"stage": 1, "score": 6}, {"stage": 3, "score": 3}):
        assert (await client.post(f"/api/contents/{cid}/listen-check", json=bad)).status_code == 422


async def test_routine_payload_reflects_before_after(client, db_session):
    user = await login(client, db_session)
    await seed_items(db_session, count=1)
    cid = await _subscribed_content_id(db_session, user.id)

    assert (await client.get(f"/api/contents/{cid}/routine")).json()["listen"] == {
        "before": None,
        "after": None,
    }

    await client.post(f"/api/contents/{cid}/listen-check", json={"stage": 1, "score": 2})
    await client.post(f"/api/contents/{cid}/listen-check", json={"stage": 2, "score": 5})
    assert (await client.get(f"/api/contents/{cid}/routine")).json()["listen"] == {
        "before": 2,
        "after": 5,
    }
