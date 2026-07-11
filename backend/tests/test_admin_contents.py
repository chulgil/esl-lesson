"""백오피스 콘텐츠 API (docs/specs/backoffice.md)."""

from sqlalchemy import select

from app.models import Content, ItemOccurrence, LearningItem, TranscriptSegment


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
    bad = await admin_client.post(
        "/api/admin/contents", json={"source": "youtube", "url": "https://example.com/x"}
    )
    assert bad.status_code == 400

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
