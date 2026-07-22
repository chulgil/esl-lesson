"""에이전트 정렬 엔드포인트 (docs/specs/word-alignment.md)."""

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import Content, ExtractionJob, TranscriptSegment

AGENT_HEADERS = {"X-Agent-Token": "test-agent-token"}


@pytest.fixture(autouse=True)
def agent_token_env(monkeypatch):
    monkeypatch.setenv("AGENT_TOKEN", "test-agent-token")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _ready_content(db, *, video="dQw4w9WgXcQ"):
    content = Content(source="youtube", youtube_video_id=video, title="T", status="ready")
    db.add(content)
    await db.flush()
    db.add(
        TranscriptSegment(
            content_id=content.id, seq=0, start_ms=0, end_ms=5000, en_text="Hi there."
        )
    )
    db.add(
        TranscriptSegment(
            content_id=content.id, seq=1, start_ms=5000, end_ms=9000, en_text="Bye now."
        )
    )
    await db.commit()
    return content


async def test_pending_alignments_lists_ready_unaligned(client, db_session):
    content = await _ready_content(db_session)
    listed = (await client.get("/api/agent/pending-alignments", headers=AGENT_HEADERS)).json()
    assert listed["items"][0]["content_id"] == content.id
    assert listed["items"][0]["segments"] == [
        {"seq": 0, "en_text": "Hi there."},
        {"seq": 1, "en_text": "Bye now."},
    ]


async def test_submit_alignment_stores_words_and_recomputes(client, db_session):
    content = await _ready_content(db_session)
    res = await client.post(
        f"/api/agent/transcripts/{content.id}/alignment",
        headers=AGENT_HEADERS,
        json={
            "alignments": {
                "0": [{"w": "Hi", "s": 120, "e": 700}, {"w": "there", "s": 700, "e": 1400}],
                "1": [{"w": "Bye", "s": 5200, "e": 5900}, {"w": "now", "s": 5900, "e": 6300}],
            }
        },
    )
    assert res.status_code == 202
    assert res.json()["aligned"] == 2

    segs = (
        (
            await db_session.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.content_id == content.id)
                .order_by(TranscriptSegment.seq)
            )
        )
        .scalars()
        .all()
    )
    assert segs[0].start_ms == 120 and segs[0].end_ms == 1400
    assert segs[0].words[0]["w"] == "Hi"

    job = (
        await db_session.execute(
            select(ExtractionJob).where(
                ExtractionJob.content_id == content.id, ExtractionJob.step == "align"
            )
        )
    ).scalar_one()
    assert job.status == "done"

    # 정렬됨 → 대기 목록에서 사라짐
    listed = (await client.get("/api/agent/pending-alignments", headers=AGENT_HEADERS)).json()
    assert listed["items"] == []


async def test_submit_alignment_idempotent(client, db_session):
    content = await _ready_content(db_session)
    body = {"alignments": {"0": [{"w": "Hi", "s": 1, "e": 2}]}}
    await client.post(
        f"/api/agent/transcripts/{content.id}/alignment", headers=AGENT_HEADERS, json=body
    )
    dup = await client.post(
        f"/api/agent/transcripts/{content.id}/alignment", headers=AGENT_HEADERS, json=body
    )
    assert dup.json().get("skipped") is True


async def test_alignment_failed_drops_from_queue(client, db_session):
    content = await _ready_content(db_session)
    res = await client.post(
        f"/api/agent/transcripts/{content.id}/alignment/failed", headers=AGENT_HEADERS
    )
    assert res.status_code == 200
    listed = (await client.get("/api/agent/pending-alignments", headers=AGENT_HEADERS)).json()
    assert listed["items"] == []


async def test_alignment_requires_token(client, db_session):
    assert (await client.get("/api/agent/pending-alignments")).status_code == 401
