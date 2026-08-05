"""콘텐츠 루틴 여정 — 6단계 체크 + 한 문장 요약 (ted-routine-2026-08.md P1)."""

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


async def test_routine_requires_subscription(client, db_session):
    await login(client, db_session)
    content = Content(source="manual", title="남의 것", status="ready", visibility="public")
    db_session.add(content)
    await db_session.commit()
    # 구독 안 한 콘텐츠 — 존재 여부도 흘리지 않는 404 (my_contents 계약)
    assert (await client.get(f"/api/contents/{content.id}/routine")).status_code == 404
    assert (await client.get("/api/contents/999999/routine")).status_code == 404


async def test_routine_steps_toggle_and_complete_xp(client, db_session):
    user = await login(client, db_session)
    await seed_items(db_session, count=1)
    cid = await _subscribed_content_id(db_session, user.id)

    res = (await client.get(f"/api/contents/{cid}/routine")).json()
    assert [s["done"] for s in res["steps"]] == [False] * 6
    assert res["completed"] is False and res["summary"] is None

    # 체크 — 멱등 (두 번 체크해도 한 행)
    for _ in range(2):
        res = await client.post(f"/api/contents/{cid}/routine/1", json={"done": True})
        assert res.status_code == 200
    assert (await client.get(f"/api/contents/{cid}/routine")).json()["steps"][0]["done"] is True

    # 체크 해제
    await client.post(f"/api/contents/{cid}/routine/1", json={"done": False})
    assert (await client.get(f"/api/contents/{cid}/routine")).json()["steps"][0]["done"] is False

    # 범위 밖 단계 — 422
    assert (
        await client.post(f"/api/contents/{cid}/routine/7", json={"done": True})
    ).status_code == 422

    # 6단계 전부 완료 → completed + 완주 보너스 XP 50
    for step in range(1, 7):
        await client.post(f"/api/contents/{cid}/routine/{step}", json={"done": True})
    res = (await client.get(f"/api/contents/{cid}/routine")).json()
    assert res["completed"] is True
    assert (await client.get("/api/study/stats")).json()["xp"] == 50


async def test_summary_submit_saves_feedback_and_checks_step6(client, db_session, monkeypatch):
    from app.api import routine as routine_api

    async def fake_feedback(db, content, text):
        assert "great" in text
        return "의미가 잘 전달돼요 — 'importance of sleep' 처럼 쓰면 더 자연스러워요"

    monkeypatch.setattr(routine_api.routine_service, "summary_feedback", fake_feedback)

    user = await login(client, db_session)
    await seed_items(db_session, count=1)
    cid = await _subscribed_content_id(db_session, user.id)

    res = await client.post(
        f"/api/contents/{cid}/summary", json={"text": "Sleep is great for the brain."}
    )
    assert res.status_code == 200
    body = res.json()
    assert "자연스러워요" in body["feedback"]

    routine = (await client.get(f"/api/contents/{cid}/routine")).json()
    assert routine["steps"][5]["done"] is True  # 요약 제출 = 6단계 자동 체크
    assert routine["summary"]["text"] == "Sleep is great for the brain."
    # 요약 제출 XP 20 (스텝 완주 아님 — 보너스 없음)
    assert (await client.get("/api/study/stats")).json()["xp"] == 20


async def test_summary_saved_even_when_llm_fails(client, db_session, monkeypatch):
    from app.api import routine as routine_api

    async def boom(db, content, text):
        raise RuntimeError("llm down")

    monkeypatch.setattr(routine_api.routine_service, "summary_feedback", boom)

    user = await login(client, db_session)
    await seed_items(db_session, count=1)
    cid = await _subscribed_content_id(db_session, user.id)

    res = await client.post(f"/api/contents/{cid}/summary", json={"text": "A short one."})
    assert res.status_code == 200
    assert res.json()["feedback"] is None  # 인출 자체가 목적 — 저장은 진행
    assert (await client.get(f"/api/contents/{cid}/routine")).json()["summary"]["text"] == (
        "A short one."
    )
