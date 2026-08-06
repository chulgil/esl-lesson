"""콘텐츠 요청 — 공급을 수요와 연결 (effectiveness-audit-2026-08.md P0-3)."""

from tests.test_study import login


async def test_request_saved_and_daily_limit(client, db_session):
    await login(client, db_session)
    for i in range(5):
        res = await client.post("/api/contents/requests", json={"text": f"쉬운 회화 영상 {i}"})
        assert res.status_code == 200 and res.json()["saved"] is True
    # 하루 5건 제한 — 남용 가드
    res = await client.post("/api/contents/requests", json={"text": "6번째"})
    assert res.status_code == 422 and res.json()["detail"] == "daily_request_limit"


async def test_admin_lists_requests_learner_cannot(admin_client, client, db_session):
    # admin_client 와 client 는 쿠키를 공유 — learner 행동을 먼저 끝낸 뒤 admin 전환
    await login(client, db_session)
    await client.post("/api/contents/requests", json={"text": "TED 초급 편"})

    from app.api.auth import upsert_google_user
    from app.core.config import get_settings
    from app.core.security import SESSION_COOKIE, create_session_token

    # learner 로는 admin 목록 403
    assert (await client.get("/api/admin/contents/requests")).status_code == 403

    admin = await upsert_google_user(
        db_session,
        {"sub": "g-admin", "email": "boss@example.com", "email_verified": True, "name": "Boss"},
        get_settings(),
    )
    client.cookies.set(SESSION_COOKIE, create_session_token(admin))
    res = await client.get("/api/admin/contents/requests")
    assert res.status_code == 200
    items = res.json()["items"]
    assert items[0]["text"] == "TED 초급 편"
    assert items[0]["nickname"]
