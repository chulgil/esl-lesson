"""파이프라인 통합: 번역 -> 추출 -> 전역 dedup (AI/유튜브 호출은 모킹)."""

import pytest
from sqlalchemy import func, select

import app.core.db as core_db
from app.models import Content, ItemOccurrence, LearningItem, TranscriptSegment
from app.services import pipeline


@pytest.fixture
async def wired_db(db_session, monkeypatch):
    """run_pipeline 이 테스트 세션 팩토리를 쓰도록 전역 엔진을 바꿔치기."""

    class FakeFactory:
        def __call__(self):
            return FakeSessionCtx()

    class FakeSessionCtx:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(core_db, "_engine", object())
    monkeypatch.setattr(core_db, "_session_factory", FakeFactory())
    monkeypatch.setattr(pipeline, "BACKOFF_BASE_SECONDS", 0)
    return db_session


EXTRACTED = {
    "words": [{"en": "resilient", "ko": "회복력 있는", "difficulty": "advanced", "segment_seq": 0}],
    "idioms": [],
    "patterns": [],
    "sentences": [
        {
            "en": "There is a tree over there.",
            "ko": "저기에 나무가 있다.",
            "thinking_ko": "있다, 나무가, 저기에",
            "segment_seq": 1,
        }
    ],
}


async def test_manual_pipeline_translate_extract_dedup(wired_db, monkeypatch):
    db = wired_db

    async def fake_translate(texts, source_lang="en"):
        return [f"번역:{t}" for t in texts]

    async def fake_extract(segments, source_lang="en"):
        return EXTRACTED

    monkeypatch.setattr(pipeline.extraction, "translate_texts", fake_translate)
    monkeypatch.setattr(pipeline.extraction, "extract_items", fake_extract)

    content = Content(source="manual", title="T1")
    db.add(content)
    await db.flush()
    db.add_all(
        [
            TranscriptSegment(content_id=content.id, seq=0, en_text="He is resilient."),
            TranscriptSegment(content_id=content.id, seq=1, en_text="There is a tree over there."),
        ]
    )
    await db.commit()

    await pipeline.run_pipeline(content.id)

    await db.refresh(content)
    assert content.status == "ready"
    segments = (
        (await db.execute(select(TranscriptSegment).order_by(TranscriptSegment.seq)))
        .scalars()
        .all()
    )
    assert all(s.ko_text and s.ko_text.startswith("번역:") for s in segments)

    items = (await db.execute(select(LearningItem))).scalars().all()
    assert {i.item_type for i in items} == {"word", "sentence"}
    sentence = next(i for i in items if i.item_type == "sentence")
    assert sentence.hint_thinking == "있다, 나무가, 저기에"
    # 관리자 큐레이션 전환 후 추출 항목은 기본 승인 (2026-07-30, content-governance.md)
    assert sentence.review_status == "approved"

    # 같은 항목이 나오는 두 번째 콘텐츠 → 항목 재사용, 출처만 추가 (전역 dedup)
    content2 = Content(source="manual", title="T2")
    db.add(content2)
    await db.flush()
    db.add(TranscriptSegment(content_id=content2.id, seq=0, en_text="Be resilient!"))
    await db.commit()
    await pipeline.run_pipeline(content2.id)

    item_count = (await db.execute(select(func.count(LearningItem.id)))).scalar_one()
    assert item_count == 2  # 늘지 않음
    occ_count = (await db.execute(select(func.count(ItemOccurrence.id)))).scalar_one()
    assert occ_count == 4


async def test_pipeline_youtube_transcript_uses_content_lang_priority(wired_db, monkeypatch):
    """content.lang 기준 자막 우선순위 — ja 콘텐츠는 ("ja",) 로 1차 fetch (다국어 학습)."""
    from app.services import youtube

    db = wired_db
    calls: list[tuple] = []

    async def fake_title(video_id):
        return "JA Title"

    def fake_transcript(video_id, languages=("en",)):
        calls.append(languages)
        if languages == ("ja",):
            return youtube.TranscriptResult(
                language="ja",
                is_generated=False,
                snippets=[
                    youtube.Snippet("こんにちは。", 0, 1000),
                    youtube.Snippet("元気ですか。", 1000, 2000),
                ],
            )
        raise youtube.TranscriptNotFoundError("no separate ko captions")

    captured: dict = {}

    async def fake_translate(texts, source_lang="en"):
        captured["translate_source_lang"] = source_lang
        return [f"번역:{t}" for t in texts]

    async def fake_extract(segments, source_lang="en"):
        captured["extract_source_lang"] = source_lang
        return EXTRACTED

    monkeypatch.setattr(pipeline.youtube, "fetch_title", fake_title)
    monkeypatch.setattr(pipeline.youtube, "fetch_transcript", fake_transcript)
    monkeypatch.setattr(pipeline.extraction, "translate_texts", fake_translate)
    monkeypatch.setattr(pipeline.extraction, "extract_items", fake_extract)

    content = Content(
        source="youtube",
        youtube_video_id="javid0000001",
        title="(제목 조회 중)",
        lang="ja",
        youtube_license="youtube",  # 라이선스 재조회 스킵
    )
    db.add(content)
    await db.commit()

    await pipeline.run_pipeline(content.id)

    await db.refresh(content)
    assert content.status == "ready"
    # 1차 fetch 는 content.lang("ja") 우선순위, en 하드코딩 아님
    assert calls[0] == ("ja",)
    # ja != ko 이므로 얼라인용 ko 자막도 시도(없으면 조용히 스킵)
    assert ("ko",) in calls
    # 번역/추출 프롬프트에도 소스 언어(ja)가 전달된다
    assert captured["translate_source_lang"] == "ja"
    assert captured["extract_source_lang"] == "ja"


async def test_pipeline_ko_content_skips_translation_step(wired_db, monkeypatch):
    """content.lang="ko" 는 번역 대상과 소스가 같아 번역 단계를 스킵한다."""
    from app.services import youtube

    db = wired_db
    calls: list[tuple] = []

    async def fake_title(video_id):
        return "KO Title"

    def fake_transcript(video_id, languages=("en",)):
        calls.append(languages)
        return youtube.TranscriptResult(
            language="ko",
            is_generated=False,
            snippets=[youtube.Snippet("안녕하세요.", 0, 1000)],
        )

    async def fail_translate(texts, source_lang="en"):
        raise AssertionError("ko 콘텐츠는 번역을 호출하면 안 된다")

    async def fake_extract(segments, source_lang="en"):
        return EXTRACTED

    monkeypatch.setattr(pipeline.youtube, "fetch_title", fake_title)
    monkeypatch.setattr(pipeline.youtube, "fetch_transcript", fake_transcript)
    monkeypatch.setattr(pipeline.extraction, "translate_texts", fail_translate)
    monkeypatch.setattr(pipeline.extraction, "extract_items", fake_extract)

    content = Content(
        source="youtube",
        youtube_video_id="kovid0000001",
        title="(제목 조회 중)",
        lang="ko",
        youtube_license="youtube",
    )
    db.add(content)
    await db.commit()

    await pipeline.run_pipeline(content.id)

    await db.refresh(content)
    assert content.status == "ready"
    # 1차 fetch 만 호출 — 이미 ko 라 별도 얼라인 fetch 불필요
    assert calls == [("ko",)]
    segments = (
        (await db.execute(select(TranscriptSegment).order_by(TranscriptSegment.seq)))
        .scalars()
        .all()
    )
    assert all(s.ko_text is None for s in segments)


async def test_pipeline_marks_failed_after_retries(wired_db, monkeypatch):
    db = wired_db

    async def boom(texts, source_lang="en"):
        raise RuntimeError("api down")

    monkeypatch.setattr(pipeline.extraction, "translate_texts", boom)

    content = Content(source="manual", title="F")
    db.add(content)
    await db.flush()
    db.add(TranscriptSegment(content_id=content.id, seq=0, en_text="Hello world."))
    await db.commit()

    await pipeline.run_pipeline(content.id)
    await db.refresh(content)
    assert content.status == "failed"
    assert "translate" in (content.error_message or "") or content.error_message
