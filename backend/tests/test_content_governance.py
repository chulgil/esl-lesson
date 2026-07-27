"""콘텐츠 거버넌스 — 담기 게이트 + 원저작자 허락 증빙 (docs/specs/content-governance.md)."""

from sqlalchemy import select

from app.models import Content, ContentPermission, ContentSubscription, ItemOccurrence, LearningItem


async def login_as(client, db, email):
    """담기 게이트 자체를 검증하므로, 기존 공용 콘텐츠를 자동으로 담지 않는 로그인."""
    from app.api.auth import upsert_google_user
    from app.core.config import get_settings
    from app.core.security import SESSION_COOKIE, create_session_token

    user = await upsert_google_user(
        db,
        {"sub": f"g-{email}", "email": email, "email_verified": True, "name": email},
        get_settings(),
    )
    client.cookies.set(SESSION_COOKIE, create_session_token(user))
    return user


YT = "https://youtu.be/dQw4w9WgXcQ"
PERMISSION = {
    "rights_holder": "Example Channel",
    "rights_holder_contact": "owner@example.com",
    "granted_at": "2026-07-20",
    "scope_transcript": True,
    "scope_translate": True,
    "scope_derive": True,
    "scope_commercial": False,
    "evidence": "2026-07-20 이메일 승낙 (보관: legal/permissions/example-channel.eml)",
}


async def make_public_content_with_item(db, en_text="governanceword"):
    """공용 콘텐츠 + approved 항목 1개. 구독은 만들지 않는다 (담기 게이트 검증용)."""
    content = Content(source="manual", title="공용 소재", visibility="public", status="ready")
    db.add(content)
    await db.flush()
    item = LearningItem(
        item_type="word",
        en_text=en_text,
        ko_text="뜻",
        normalized_key=en_text,
        review_status="approved",
    )
    db.add(item)
    await db.flush()
    db.add(ItemOccurrence(item_id=item.id, content_id=content.id))
    await db.commit()
    return content, item


# --- 담기 게이트 -------------------------------------------------------------


async def test_public_items_hidden_until_subscribed(client, db_session):
    """공용 콘텐츠도 담아야 학습 큐에 들어온다 (2026-07-27 규칙 변경)."""
    content, _ = await make_public_content_with_item(db_session)
    await login_as(client, db_session, "u@example.com")

    before = (await client.get("/api/study/queue")).json()
    assert before["questions"] == []

    assert (await client.post(f"/api/my/contents/{content.id}/subscribe")).status_code == 202
    after = (await client.get("/api/study/queue")).json()
    assert len(after["questions"]) == 1


async def test_unsubscribe_removes_items_from_queue(client, db_session):
    content, _ = await make_public_content_with_item(db_session)
    await login_as(client, db_session, "u@example.com")
    await client.post(f"/api/my/contents/{content.id}/subscribe")
    assert len((await client.get("/api/study/queue")).json()["questions"]) == 1

    assert (await client.delete(f"/api/my/contents/{content.id}")).status_code == 204
    assert (await client.get("/api/study/queue")).json()["questions"] == []


async def test_library_exposes_subscribed_flag(client, db_session):
    content, _ = await make_public_content_with_item(db_session)
    await login_as(client, db_session, "u@example.com")

    listed = (await client.get("/api/contents")).json()
    assert [c["subscribed"] for c in listed["items"]] == [False]
    assert (await client.get(f"/api/contents/{content.id}")).json()["subscribed"] is False

    await client.post(f"/api/my/contents/{content.id}/subscribe")
    listed = (await client.get("/api/contents")).json()
    assert [c["subscribed"] for c in listed["items"]] == [True]
    assert (await client.get(f"/api/contents/{content.id}")).json()["subscribed"] is True


async def test_user_cannot_retry_public_content(client, db_session):
    """담기가 열려도 관리자 콘텐츠의 AI 재추출은 사용자가 트리거할 수 없다."""
    content, _ = await make_public_content_with_item(db_session)
    await login_as(client, db_session, "u@example.com")
    await client.post(f"/api/my/contents/{content.id}/subscribe")

    assert (await client.post(f"/api/my/contents/{content.id}/retry")).status_code == 403


async def test_user_can_retry_own_private_content(client, db_session):
    """잔존 개인 콘텐츠는 계속 재시도 가능."""
    user = await login_as(client, db_session, "u@example.com")
    content = Content(source="manual", title="개인", visibility="private", status="failed")
    db_session.add(content)
    await db_session.flush()
    db_session.add(ContentSubscription(content_id=content.id, user_id=user.id))
    await db_session.commit()

    assert (await client.post(f"/api/my/contents/{content.id}/retry")).status_code == 202


# --- 허락 증빙 게이트 ---------------------------------------------------------


async def test_non_cc_without_permission_is_blocked(admin_client, db_session):
    res = await admin_client.post("/api/admin/contents", json={"source": "youtube", "url": YT})
    assert res.status_code == 409
    assert res.json()["detail"] == "cc_required"
    assert (await db_session.execute(select(Content.id))).scalars().all() == []


async def test_non_cc_with_permission_is_recorded(admin_client, db_session):
    res = await admin_client.post(
        "/api/admin/contents", json={"source": "youtube", "url": YT, "permission": PERMISSION}
    )
    assert res.status_code == 202

    perm = (await db_session.execute(select(ContentPermission))).scalar_one()
    assert perm.content_id == res.json()["id"]
    assert perm.rights_holder == "Example Channel"
    assert perm.granted_at.isoformat() == "2026-07-20"
    assert perm.scope_translate is True
    assert perm.scope_commercial is False
    assert perm.recorded_by is not None


async def test_partial_scope_is_rejected_without_creating_content(admin_client, db_session):
    """번역 허락이 빠지면 파이프라인이 허락 범위를 벗어난다 — 등록 거부, 고아 콘텐츠도 없음."""
    partial = {**PERMISSION, "scope_translate": False}
    res = await admin_client.post(
        "/api/admin/contents", json={"source": "youtube", "url": YT, "permission": partial}
    )
    assert res.status_code == 422
    assert res.json()["detail"] == "permission_scope_insufficient"
    assert (await db_session.execute(select(Content.id))).scalars().all() == []
    assert (await db_session.execute(select(ContentPermission.id))).scalars().all() == []


async def test_admin_detail_exposes_permission(admin_client, db_session):
    created = await admin_client.post(
        "/api/admin/contents", json={"source": "youtube", "url": YT, "permission": PERMISSION}
    )
    detail = (await admin_client.get(f"/api/admin/contents/{created.json()['id']}")).json()
    assert detail["permission"]["rights_holder"] == "Example Channel"
    assert detail["permission"]["scope_derive"] is True


async def test_cc_video_needs_no_permission(admin_client, db_session, monkeypatch):
    """CC 라이선스는 그 자체가 이용허락 — 증빙 없이 통과."""
    from app.services import youtube

    async def fake_license(video_id):
        return "creativeCommons"

    monkeypatch.setattr(youtube, "fetch_license", fake_license)
    res = await admin_client.post("/api/admin/contents", json={"source": "youtube", "url": YT})
    assert res.status_code == 202
    assert (await db_session.execute(select(ContentPermission.id))).scalars().all() == []
