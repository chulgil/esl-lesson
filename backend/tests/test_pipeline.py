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

    async def fake_translate(texts):
        return [f"번역:{t}" for t in texts]

    async def fake_extract(segments):
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


async def test_pipeline_marks_failed_after_retries(wired_db, monkeypatch):
    db = wired_db

    async def boom(texts):
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
