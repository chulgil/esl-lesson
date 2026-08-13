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
        admin_mod.youtube, "fetch_license", new=AsyncMock(return_value="creativeCommon")
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


async def test_admin_content_summary_and_detail_expose_lang(admin_client, db_session):
    content = Content(source="manual", title="T", lang="ko", visibility="public", status="ready")
    db_session.add(content)
    await db_session.commit()

    listed = await admin_client.get("/api/admin/contents")
    item = next(i for i in listed.json()["items"] if i["id"] == content.id)
    assert item["lang"] == "ko"

    detail = await admin_client.get(f"/api/admin/contents/{content.id}")
    assert detail.json()["lang"] == "ko"


async def test_create_content_accepts_lang_and_rejects_invalid(admin_client, db_session):
    """등록 body 의 lang(en/ja/ko, 기본 en) 이 저장되고 그 외 값은 422 (다국어 학습)."""
    ok = await admin_client.post(
        "/api/admin/contents",
        json={
            "source": "manual",
            "title": "日本語スクリプト",
            "script_en": "こんにちは。",
            "lang": "ja",
        },
    )
    assert ok.status_code == 202
    row = await db_session.get(Content, ok.json()["id"])
    assert row.lang == "ja"

    default_lang = await admin_client.post(
        "/api/admin/contents",
        json={"source": "manual", "title": "No lang field", "script_en": "Hello."},
    )
    assert default_lang.status_code == 202
    default_row = await db_session.get(Content, default_lang.json()["id"])
    assert default_row.lang == "en"

    bad = await admin_client.post(
        "/api/admin/contents",
        json={"source": "manual", "title": "Bad lang", "script_en": "Hello.", "lang": "fr"},
    )
    assert bad.status_code == 422


async def test_create_youtube_content_auto_detects_lang_from_data_api(admin_client, db_session):
    """Data API defaultAudioLanguage 감지 시 body 기본값(en) 대신 감지값을 반영."""
    from unittest.mock import AsyncMock, patch

    import app.api.admin_contents as admin_mod

    with (
        patch.object(
            admin_mod.youtube, "fetch_license", new=AsyncMock(return_value="creativeCommon")
        ),
        patch.object(admin_mod.youtube, "fetch_video_lang", new=AsyncMock(return_value="ja")),
    ):
        res = await admin_client.post(
            "/api/admin/contents",
            json={"source": "youtube", "url": "https://youtu.be/jadetect0001"},
        )
    assert res.status_code == 202
    row = await db_session.get(Content, res.json()["id"])
    assert row.lang == "ja"


async def test_create_youtube_content_falls_back_to_body_lang_when_undetected(
    admin_client, db_session
):
    """Data API 감지 실패(None) 시 body 에 명시한 lang 값을 그대로 사용."""
    from unittest.mock import AsyncMock, patch

    import app.api.admin_contents as admin_mod

    with (
        patch.object(
            admin_mod.youtube, "fetch_license", new=AsyncMock(return_value="creativeCommon")
        ),
        patch.object(admin_mod.youtube, "fetch_video_lang", new=AsyncMock(return_value=None)),
    ):
        res = await admin_client.post(
            "/api/admin/contents",
            json={"source": "youtube", "url": "https://youtu.be/nodetect00001", "lang": "ko"},
        )
    assert res.status_code == 202
    row = await db_session.get(Content, res.json()["id"])
    assert row.lang == "ko"


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
        admin_mod.youtube, "fetch_license", new=AsyncMock(return_value="creativeCommon")
    ):
        promoted = await admin_client.post(
            "/api/admin/contents",
            json={"source": "youtube", "url": "https://youtu.be/privvid0001"},
        )
        assert promoted.status_code == 202
        assert promoted.json()["promoted"] is True
    await db_session.refresh(private)
    assert private.visibility == "public"
    assert private.youtube_license == "creativeCommon"


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


async def test_patch_item_text_change_invalidates_insight_and_embedding(
    admin_client, db_session, monkeypatch
):
    """항목 텍스트 정정 시 파생 캐시 무효화 — 인사이트 삭제 + 임베딩 드롭
    (2026-08-13 flow 감사 F2·F3: 정정 후에도 옛 텍스트 기반 캐시가 영구 잔존하던 문제)."""
    from app.models import WordInsight

    dropped: list[int] = []

    async def fake_drop(db, item_id):
        dropped.append(item_id)

    import app.api.admin_contents as admin_module

    monkeypatch.setattr(admin_module.embeddings, "drop_item_embedding", fake_drop)

    item = LearningItem(
        item_type="word", en_text="resilient", ko_text="회복력 있는", normalized_key="resilient"
    )
    db_session.add(item)
    await db_session.flush()
    db_session.add(WordInsight(item_id=item.id, payload={"ipa": "old"}, model="test"))
    await db_session.commit()

    # 텍스트와 무관한 변경(review_status)은 캐시 유지
    res = await admin_client.patch(
        f"/api/admin/items/{item.id}", json={"review_status": "approved"}
    )
    assert res.status_code == 200
    kept = (
        await db_session.execute(select(WordInsight).where(WordInsight.item_id == item.id))
    ).scalar_one_or_none()
    assert kept is not None
    assert dropped == []

    # en_text 정정 → 인사이트 삭제 + 임베딩 드롭
    res = await admin_client.patch(f"/api/admin/items/{item.id}", json={"en_text": "resilience"})
    assert res.status_code == 200
    gone = (
        await db_session.execute(select(WordInsight).where(WordInsight.item_id == item.id))
    ).scalar_one_or_none()
    assert gone is None
    assert dropped == [item.id]


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


async def test_public_duplicate_registration_rejected(admin_client, db_session):
    """이미 공용으로 등록된 영상 재등록 → 409 (연속 등록 시 중복 방지, 2026-08-11)."""
    from unittest.mock import AsyncMock, patch

    from app.api import admin_contents as admin_mod
    from app.models import Content

    db_session.add(
        Content(
            source="youtube",
            visibility="public",
            youtube_video_id="pubvid00001",
            url="https://youtu.be/pubvid00001",
            title="공용 영상",
            status="ready",
        )
    )
    await db_session.commit()

    with patch.object(
        admin_mod.youtube, "fetch_license", new=AsyncMock(return_value="creativeCommon")
    ):
        res = await admin_client.post(
            "/api/admin/contents",
            json={"source": "youtube", "url": "https://youtu.be/pubvid00001"},
        )
    assert res.status_code == 409
    assert res.json()["detail"] == "already_registered"


async def test_cc_search_marks_registered_videos(admin_client, db_session, monkeypatch):
    """검색 결과에 이미 등록된 영상 표시 — 연속 등록 시 중복 후보 제거."""
    from app.api import admin_contents
    from app.models import Content

    db_session.add(
        Content(
            source="youtube",
            visibility="public",
            youtube_video_id="regvid00001",
            url="https://youtu.be/regvid00001",
            title="등록된 영상",
            status="ready",
        )
    )
    await db_session.commit()

    async def fake_search(query, page_token=None):
        return {
            "items": [
                {"video_id": "regvid00001", "title": "Registered"},
                {"video_id": "newvid00001", "title": "Fresh"},
            ],
            "next_page_token": None,
        }

    monkeypatch.setattr(admin_contents.youtube, "search_cc_videos", fake_search)
    res = await admin_client.get("/api/admin/youtube/cc-search", params={"q": "x"})
    assert res.status_code == 200
    by_id = {i["video_id"]: i for i in res.json()["items"]}
    assert by_id["regvid00001"]["registered"] is True
    assert by_id["newvid00001"]["registered"] is False


async def test_cc_search_returns_mapped_items_with_paging(admin_client, monkeypatch):
    """CC 검색 — Data API 응답 매핑 + page_token 전달 + next_page_token 반환."""
    from app.api import admin_contents

    async def fake_search(query, page_token=None):
        assert query == "cooking"
        assert page_token == "PT1"
        return {
            "items": [
                {
                    "video_id": "abc123def45",
                    "title": "CC Cooking",
                    "channel_title": "Chef",
                    "published_at": "2026-01-01T00:00:00Z",
                    "thumbnail_url": "https://i.ytimg.com/vi/abc123def45/mqdefault.jpg",
                }
            ],
            "next_page_token": "PT2",
        }

    monkeypatch.setattr(admin_contents.youtube, "search_cc_videos", fake_search)
    res = await admin_client.get(
        "/api/admin/youtube/cc-search", params={"q": "cooking", "page_token": "PT1"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["items"][0]["video_id"] == "abc123def45"
    assert data["items"][0]["channel_title"] == "Chef"
    assert data["next_page_token"] == "PT2"


def test_cc_search_language_filter():
    """언어 메타 판정 — 명시적 비영어만 제외, 미표기는 통과 (2026-08-05)."""
    from app.services.youtube import is_language_ok

    assert is_language_ok("en") is True
    assert is_language_ok("en-US") is True
    assert is_language_ok("EN-GB") is True
    assert is_language_ok(None) is True  # 미표기 — 메타 없는 영어 영상이 많다
    assert is_language_ok("") is True
    assert is_language_ok("ko") is False
    assert is_language_ok("ja") is False


async def test_cc_search_without_api_key_returns_503(admin_client, monkeypatch):
    from app.api import admin_contents

    async def no_key(query, page_token=None):
        return None

    monkeypatch.setattr(admin_contents.youtube, "search_cc_videos", no_key)
    res = await admin_client.get("/api/admin/youtube/cc-search", params={"q": "x"})
    assert res.status_code == 503


async def test_cc_search_requires_admin(client, db_session):
    from app.api.auth import upsert_google_user
    from app.core.config import get_settings
    from app.core.security import SESSION_COOKIE, create_session_token

    learner = await upsert_google_user(
        db_session,
        {"sub": "g-cc", "email": "cc@example.com", "email_verified": True, "name": "C"},
        get_settings(),
    )
    client.cookies.set(SESSION_COOKIE, create_session_token(learner))
    res = await client.get("/api/admin/youtube/cc-search", params={"q": "x"})
    assert res.status_code == 403


async def test_dashboard_supply_metrics(admin_client, db_session):
    """공급 리듬 위젯 (P0-B): 이번 주 등록 수 + 레벨별 콘텐츠 수를 대시보드가 준다."""
    from tests.test_contents_list_difficulty import add_segments, make_content

    short = await make_content(db_session, "초급물", ["intermediate"] * 10)  # 힌트 1.0
    await add_segments(db_session, short, ["Hi there.", "How are you?"])  # 짧은 문장 → 초급

    res = await admin_client.get("/api/admin/dashboard")
    assert res.status_code == 200
    body = res.json()
    assert body["supply_goal"] == 2
    assert body["weekly_supply"] >= 1  # 방금 등록분이 이번 주로 잡힘
    assert body["levels"]["beginner"] >= 1
    assert set(body["levels"]) == {"beginner", "intermediate", "advanced"}
