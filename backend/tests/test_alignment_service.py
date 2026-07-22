"""단어 정렬 저장/경계 재계산 (docs/specs/word-alignment.md)."""

from app.models import ExtractionJob, TranscriptSegment


async def test_segment_stores_words_json(db_session):
    seg = TranscriptSegment(content_id=1, seq=0, start_ms=0, end_ms=2000, en_text="Hello world.")
    seg.words = [{"w": "Hello", "s": 100, "e": 500}, {"w": "world", "s": 500, "e": 900}]
    db_session.add(seg)
    await db_session.commit()
    await db_session.refresh(seg)
    assert seg.words[0]["w"] == "Hello"


async def test_extraction_job_accepts_align_step(db_session):
    job = ExtractionJob(content_id=1, step="align", status="pending")
    db_session.add(job)
    await db_session.commit()  # CHECK 제약 통과해야 함
    assert job.step == "align"
