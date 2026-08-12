"""라이브러리 상세 API 의 단어 시각 노출 (docs/specs/word-alignment.md)."""

from app.models import Content, ContentSubscription, TranscriptSegment
from tests.test_my_contents import login_as


async def test_library_detail_exposes_words(client, db_session):
    user = await login_as(client, db_session, "u1@example.com")
    content = Content(
        source="youtube",
        youtube_video_id="vid00000001",
        title="T",
        visibility="private",
        status="ready",
        created_by=user.id,
    )
    db_session.add(content)
    await db_session.flush()

    db_session.add(ContentSubscription(content_id=content.id, user_id=user.id))
    seg = TranscriptSegment(
        content_id=content.id, seq=0, start_ms=100, end_ms=1400, en_text="Hi there."
    )
    seg.words = [{"w": "Hi", "s": 100, "e": 700}, {"w": "there", "s": 700, "e": 1400}]
    db_session.add(seg)
    await db_session.commit()

    detail = (await client.get(f"/api/contents/{content.id}")).json()
    assert detail["segments"][0]["words"][1] == {"w": "there", "s": 700, "e": 1400}


async def test_library_list_and_detail_expose_lang(client, db_session):
    """다국어 학습: 목록·상세 응답에 콘텐츠 언어(lang) 노출 (docs/specs/chat-translation.md)."""
    user = await login_as(client, db_session, "u1@example.com")
    content = Content(
        source="youtube",
        youtube_video_id="vid00000003",
        title="T",
        lang="ja",
        visibility="private",
        status="ready",
        created_by=user.id,
    )
    db_session.add(content)
    await db_session.flush()
    db_session.add(ContentSubscription(content_id=content.id, user_id=user.id))
    await db_session.commit()

    listed = (await client.get("/api/contents")).json()
    item = next(i for i in listed["items"] if i["id"] == content.id)
    assert item["lang"] == "ja"

    detail = (await client.get(f"/api/contents/{content.id}")).json()
    assert detail["lang"] == "ja"


async def test_library_detail_words_null_when_unaligned(client, db_session):
    user = await login_as(client, db_session, "u1@example.com")
    content = Content(
        source="youtube",
        youtube_video_id="vid00000002",
        title="T",
        visibility="private",
        status="ready",
        created_by=user.id,
    )
    db_session.add(content)
    await db_session.flush()

    db_session.add(ContentSubscription(content_id=content.id, user_id=user.id))
    db_session.add(
        TranscriptSegment(content_id=content.id, seq=0, start_ms=0, end_ms=1000, en_text="Hi.")
    )
    await db_session.commit()

    detail = (await client.get(f"/api/contents/{content.id}")).json()
    assert detail["segments"][0]["words"] is None
