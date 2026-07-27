"""백오피스 콘텐츠 API (docs/specs/backoffice.md)."""

from sqlalchemy import select

from app.models import Content, ItemOccurrence, LearningItem, TranscriptSegment
from tests.test_content_governance import PERMISSION


async def test_admin_routes_require_admin(client, db_session):
    from app.api.auth import upsert_google_user
    from app.core.config import get_settings
    from app.core.security import SESSION_COOKIE, create_session_token

    learner = await upsert_google_user(
        db_session,
        {"sub": "g-l", "email": "l@example.com", "email_verified": True, "name": "L"},
        get_settings(),
    )
    client.cookies.set(SESSION_COOKIE, create_session_token(learner))
    res = await client.get("/api/admin/contents")
    assert res.status_code == 403


async def test_create_manual_content_splits_segments(admin_client, db_session):
    res = await admin_client.post(
        "/api/admin/contents",
        json={
            "source": "manual",
            "title": "Test Script",
            "script_en": "Hello there. This is a test. Goodbye!",
            "script_ko": "안녕하세요. 테스트입니다. 안녕히!",
        },
    )
    assert res.status_code == 202
    content_id = res.json()["id"]
    segments = (
        (
            await db_session.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.content_id == content_id)
                .order_by(TranscriptSegment.seq)
            )
        )
        .scalars()
        .all()
    )
    assert [s.en_text for s in segments] == ["Hello there.", "This is a test.", "Goodbye!"]
    assert segments[1].ko_text == "테스트입니다."


async def test_create_youtube_content_validates_and_dedups(admin_client, db_session):
    from unittest.mock import AsyncMock, patch

    import app.api.admin_contents as admin_mod

    bad = await admin_client.post(
        "/api/admin/contents", json={"source": "youtube", "url": "https://example.com/x"}
    )
    assert bad.status_code == 400

    with patch.object(
        admin_mod.youtube, "fetch_license", new=AsyncMock(return_value="creativeCommons")
    ):
        ok = await admin_client.post(
            "/api/admin/contents",
            json={"source": "youtube", "url": "https://youtu.be/dQw4w9WgXcQ"},
        )
        assert ok.status_code == 202

        dup = await admin_client.post(
            "/api/admin/contents",
            json={"source": "youtube", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert dup.status_code == 409


async def test_public_promotion_requires_cc_license(admin_client, db_session):
    """공용 승격 CC 게이트 — CC 아니면(미확인 포함) 409, 허락 증빙으로만 우회."""
    from unittest.mock import AsyncMock, patch

    import app.api.admin_contents as admin_mod
    from app.models import Content

    # 표준 라이선스 → 차단
    with patch.object(admin_mod.youtube, "fetch_license", new=AsyncMock(return_value="youtube")):
        blocked = await admin_client.post(
            "/api/admin/contents",
            json={"source": "youtube", "url": "https://youtu.be/aaaaaaaaaa1"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == "cc_required"

        # 원저작자 허락 증빙 첨부 시 → 등록 + 라이선스 저장
        forced = await admin_client.post(
            "/api/admin/contents",
            json={
                "source": "youtube",
                "url": "https://youtu.be/aaaaaaaaaa1",
                "permission": PERMISSION,
            },
        )
        assert forced.status_code == 202
        row = await db_session.get(Content, forced.json()["id"])
        assert row.youtube_license == "youtube"

    # 라이선스 미확인(키 없음/조회 실패)도 안전 기본값으로 차단
    with patch.object(admin_mod.youtube, "fetch_license", new=AsyncMock(return_value=None)):
        unknown = await admin_client.post(
            "/api/admin/contents",
            json={"source": "youtube", "url": "https://youtu.be/aaaaaaaaaa2"},
        )
        assert unknown.status_code == 409


async def test_private_promotion_also_gated_by_cc(admin_client, db_session):
    """개인 콘텐츠의 공용 승격도 같은 게이트를 통과해야 한다."""
    from unittest.mock import AsyncMock, patch

    import app.api.admin_contents as admin_mod
    from app.models import Content, User

    # 쿠키를 건드리지 않도록 소유자는 DB 로 직접 생성 (login 은 admin 세션을 덮어씀)
    owner = User(google_sub="g-owner", email="private-owner@example.com", name="Owner")
    db_session.add(owner)
    await db_session.flush()
    private = Content(
        source="youtube",
        visibility="private",
        youtube_video_id="privvid0001",
        url="https://youtu.be/privvid0001",
        title="개인 영상",
        status="ready",
        created_by=owner.id,
    )
    db_session.add(private)
    await db_session.commit()

    with patch.object(admin_mod.youtube, "fetch_license", new=AsyncMock(return_value="youtube")):
        blocked = await admin_client.post(
            "/api/admin/contents",
            json={"source": "youtube", "url": "https://youtu.be/privvid0001"},
        )
        assert blocked.status_code == 409

    with patch.object(
        admin_mod.youtube, "fetch_license", new=AsyncMock(return_value="creativeCommons")
    ):
        promoted = await admin_client.post(
            "/api/admin/contents",
            json={"source": "youtube", "url": "https://youtu.be/privvid0001"},
        )
        assert promoted.status_code == 202
        assert promoted.json()["promoted"] is True
    await db_session.refresh(private)
    assert private.visibility == "public"
    assert private.youtube_license == "creativeCommons"


async def test_sentence_approval_requires_thinking_hint(admin_client, db_session):
    item = LearningItem(
        item_type="sentence",
        en_text="There is a tree.",
        ko_text="나무가 있다.",
        normalized_key="there is a tree.",
        hint_thinking=None,
    )
    db_session.add(item)
    await db_session.commit()

    res = await admin_client.patch(
        f"/api/admin/items/{item.id}", json={"review_status": "approved"}
    )
    assert res.status_code == 422

    res = await admin_client.patch(
        f"/api/admin/items/{item.id}",
        json={"review_status": "approved", "hint_thinking": "있다, 나무가"},
    )
    assert res.status_code == 200
    assert res.json()["review_status"] == "approved"


async def test_approve_all_skips_hintless_sentences(admin_client, db_session):
    content = Content(source="manual", title="T")
    db_session.add(content)
    await db_session.flush()
    word = LearningItem(
        item_type="word", en_text="resilient", ko_text="회복력 있는", normalized_key="resilient"
    )
    sentence = LearningItem(
        item_type="sentence",
        en_text="No hint here.",
        ko_text="힌트 없음",
        normalized_key="no hint here.",
    )
    db_session.add_all([word, sentence])
    await db_session.flush()
    db_session.add_all(
        [
            ItemOccurrence(item_id=word.id, content_id=content.id),
            ItemOccurrence(item_id=sentence.id, content_id=content.id),
        ]
    )
    await db_session.commit()

    res = await admin_client.post(f"/api/admin/contents/{content.id}/approve-all")
    assert res.status_code == 200
    assert res.json() == {"approved": 1, "skipped": 1}
