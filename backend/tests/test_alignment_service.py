"""단어 정렬 저장/경계 재계산 (docs/specs/word-alignment.md)."""

from app.models import ExtractionJob, TranscriptSegment
from app.services.alignment import apply_alignment


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


def _seg(seq, start, end, text="x"):
    return TranscriptSegment(content_id=1, seq=seq, start_ms=start, end_ms=end, en_text=text)


def test_apply_alignment_recomputes_bounds_and_stores_words():
    segs = [_seg(0, 0, 5000), _seg(1, 5000, 9000)]
    alignments = {
        0: [{"w": "Hi", "s": 120, "e": 700}, {"w": "there", "s": 700, "e": 1400}],
        1: [{"w": "Bye", "s": 5200, "e": 5900}],
    }
    updated = apply_alignment(segs, alignments)
    assert updated == 2
    assert segs[0].start_ms == 120 and segs[0].end_ms == 1400
    assert segs[1].start_ms == 5200 and segs[1].end_ms == 5900
    assert segs[0].words[1]["w"] == "there"


def test_apply_alignment_clamps_overlap_between_neighbors():
    segs = [_seg(0, 0, 5000), _seg(1, 5000, 9000)]
    # seg1 시작이 seg0 끝보다 앞 — 겹침 → seg0.end 를 seg1.start 로 절단
    alignments = {
        0: [{"w": "a", "s": 0, "e": 3000}],
        1: [{"w": "b", "s": 2500, "e": 6000}],
    }
    apply_alignment(segs, alignments)
    assert segs[0].end_ms == 2500


def test_apply_alignment_ignores_unknown_seq_and_empty():
    segs = [_seg(0, 0, 5000)]
    updated = apply_alignment(segs, {9: [{"w": "x", "s": 0, "e": 1}], 0: []})
    assert updated == 0
    assert segs[0].words is None
