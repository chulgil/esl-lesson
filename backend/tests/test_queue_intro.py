"""신규 카드 도입 순서 — 같은 레벨 안에서 음성 연계(media) 우선.

첫 세션에 "원어민 발화로 듣는 카드"가 반드시 섞이게 — 차별점을 운이 아니라
설계로 (docs/proposal/effectiveness-audit-2026-08.md P0-1).
"""

from app.models import (
    Content,
    ContentSubscription,
    ItemOccurrence,
    LearningItem,
    TranscriptSegment,
)
from tests.test_study import login, seed_items


async def test_new_intro_prefers_items_with_media(client, db_session):
    user = await login(client, db_session)

    # 음성 연계 항목을 먼저 생성 (id 가 낮음 — 기본 최신순 정렬로는 뒤로 밀림)
    content = Content(
        source="youtube",
        title="media",
        status="ready",
        visibility="public",
        youtube_video_id="abc123def45",
    )
    db_session.add(content)
    await db_session.flush()
    db_session.add(ContentSubscription(content_id=content.id, user_id=user.id))
    item_media = LearningItem(
        item_type="word",
        en_text="mediaword",
        ko_text="뜻",
        normalized_key="mediaword",
        review_status="approved",
    )
    db_session.add(item_media)
    await db_session.flush()
    segment = TranscriptSegment(
        content_id=content.id, seq=0, start_ms=1000, end_ms=3000, en_text="mediaword here"
    )
    db_session.add(segment)
    await db_session.flush()
    db_session.add(
        ItemOccurrence(item_id=item_media.id, content_id=content.id, segment_id=segment.id)
    )
    await db_session.commit()

    # 텍스트 전용 항목을 나중에 생성 (id 높음 — 기본 정렬로는 앞)
    plain = (await seed_items(db_session, count=1))[0]

    res = (await client.get("/api/study/queue")).json()
    ids = [q["item_id"] for q in res["questions"]]
    # 같은 레벨(word) 안에서 음성 연계가 최신(plain)보다 앞
    assert ids.index(item_media.id) < ids.index(plain.id)
    media_q = next(q for q in res["questions"] if q["item_id"] == item_media.id)
    assert media_q["media"] is not None
