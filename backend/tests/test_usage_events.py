"""사용 이벤트 수집 (P1-D 관측 격차 해소 — docs/specs/usage-events.md)."""

from sqlalchemy import select

from app.models import UsageEvent
from tests.test_study import login


async def test_event_logged_with_meta(client, db_session):
    user = await login(client, db_session)
    res = await client.post("/api/events", json={"kind": "review_add", "meta": {"game": "tetris"}})
    assert res.status_code == 204
    row = (await db_session.execute(select(UsageEvent))).scalar_one()
    assert row.user_id == user.id
    assert row.kind == "review_add"
    assert row.meta == {"game": "tetris"}


async def test_unknown_kind_rejected(client, db_session):
    await login(client, db_session)
    res = await client.post("/api/events", json={"kind": "totally_new_thing"})
    assert res.status_code == 422


async def test_oversized_meta_rejected(client, db_session):
    await login(client, db_session)
    res = await client.post(
        "/api/events",
        json={"kind": "method_view", "meta": {f"k{i}": "v" for i in range(9)}},
    )
    assert res.status_code == 422


async def test_requires_login(client):
    res = await client.post("/api/events", json={"kind": "method_view"})
    assert res.status_code == 401
