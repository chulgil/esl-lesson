"""로컬 자막 수집기 API + 차단 시 대기 상태 (docs/specs/content-pipeline.md)."""

import pytest
from sqlalchemy import select

import app.core.db as core_db
from app.core.config import get_settings
from app.models import Content, ExtractionJob, TranscriptSegment
from app.services import pipeline
from app.services.youtube import TranscriptBlockedError

AGENT_HEADERS = {"X-Agent-Token": "test-agent-token"}


@pytest.fixture(autouse=True)
def agent_token_env(monkeypatch):
    monkeypatch.setenv("AGENT_TOKEN", "test-agent-token")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def wired_db(db_session, monkeypatch):
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


async def make_blocked_content(db) -> Content:
    content = Content(
        source="youtube", youtube_video_id="dQw4w9WgXcQ", title="T", visibility="private"
    )
    db.add(content)
    await db.flush()
    db.add(ExtractionJob(content_id=content.id, step="metadata", status="done"))
    db.add(ExtractionJob(content_id=content.id, step="transcript", status="failed"))
    await db.commit()
    return content


async def test_blocked_pipeline_holds_content_in_waiting(wired_db, monkeypatch):
    def blocked(*args, **kwargs):
        raise TranscriptBlockedError("blocked")

    monkeypatch.setattr(pipeline.youtube, "fetch_transcript", blocked)

    async def fake_title(video_id):
        return "제목"

    monkeypatch.setattr(pipeline.youtube, "fetch_title", fake_title)

    content = Content(source="youtube", youtube_video_id="dQw4w9WgXcQ", title="T")
    wired_db.add(content)
    await wired_db.commit()

    await pipeline.run_pipeline(content.id)
    await wired_db.refresh(content)
    assert content.status == "pending"  # failed 가 아니라 대기
    assert "자막 준비 중" in (content.error_message or "")


async def test_blocked_pipeline_exposes_content_to_agent(client, wired_db, monkeypatch):
    """차단 시 transcript 잡이 failed 로 남아야 수집기 대기 목록에 잡힌다 (교착 회귀 방지).

    잡이 running 으로 방치되면 pending-transcripts 필터(failed 잡)에 영원히
    안 걸려 수집기가 콘텐츠를 못 본다 — 2026-07-15 프로덕션 실측 교착.
    """

    def blocked(*args, **kwargs):
        raise TranscriptBlockedError("blocked")

    monkeypatch.setattr(pipeline.youtube, "fetch_transcript", blocked)

    async def fake_title(video_id):
        return "제목"

    monkeypatch.setattr(pipeline.youtube, "fetch_title", fake_title)

    content = Content(source="youtube", youtube_video_id="dQw4w9WgXcQ", title="T")
    wired_db.add(content)
    await wired_db.commit()

    await pipeline.run_pipeline(content.id)

    job = (
        await wired_db.execute(
            select(ExtractionJob).where(
                ExtractionJob.content_id == content.id, ExtractionJob.step == "transcript"
            )
        )
    ).scalar_one()
    assert job.status == "failed"  # running 방치 금지 — 수집기 노출 조건
    assert job.error

    listed = (await client.get("/api/agent/pending-transcripts", headers=AGENT_HEADERS)).json()
    assert listed["items"] == [{"content_id": content.id, "youtube_video_id": "dQw4w9WgXcQ"}]


async def test_missing_report_finalizes_content_and_leaves_list(client, db_session):
    """수집기가 '영어 자막 없음'을 확정 보고하면 실패 종결 + 대기 목록 제거."""
    content = await make_blocked_content(db_session)

    res = await client.post(f"/api/agent/transcripts/{content.id}/missing", headers=AGENT_HEADERS)
    assert res.status_code == 200
    assert res.json()["status"] == "failed"

    await db_session.refresh(content)
    assert content.status == "failed"
    assert "자막" in (content.error_message or "")

    listed = (await client.get("/api/agent/pending-transcripts", headers=AGENT_HEADERS)).json()
    assert listed["items"] == []


async def test_missing_report_skipped_when_segments_exist(client, db_session):
    """이미 자막이 제출된 콘텐츠에 대한 뒤늦은 '없음' 보고는 무시 (경합 보호)."""
    content = await make_blocked_content(db_session)
    db_session.add(
        TranscriptSegment(content_id=content.id, seq=0, start_ms=0, end_ms=1000, en_text="Hi.")
    )
    await db_session.commit()

    res = await client.post(f"/api/agent/transcripts/{content.id}/missing", headers=AGENT_HEADERS)
    assert res.status_code == 200
    assert res.json().get("skipped") is True

    await db_session.refresh(content)
    assert content.status == "pending"  # 실패로 덮어쓰지 않음


async def test_agent_endpoints_require_token(client, db_session):
    assert (await client.get("/api/agent/pending-transcripts")).status_code == 401
    bad = await client.get("/api/agent/pending-transcripts", headers={"X-Agent-Token": "wrong"})
    assert bad.status_code == 401


async def test_agent_disabled_without_token_config(client, monkeypatch):
    monkeypatch.delenv("AGENT_TOKEN", raising=False)
    get_settings.cache_clear()
    res = await client.get("/api/agent/pending-transcripts", headers=AGENT_HEADERS)
    assert res.status_code == 404


async def test_pending_list_and_submit_flow(client, db_session):
    content = await make_blocked_content(db_session)

    listed = (await client.get("/api/agent/pending-transcripts", headers=AGENT_HEADERS)).json()
    assert listed["items"] == [{"content_id": content.id, "youtube_video_id": "dQw4w9WgXcQ"}]

    res = await client.post(
        f"/api/agent/transcripts/{content.id}",
        headers=AGENT_HEADERS,
        json={
            "en_snippets": [
                {"text": "Hello everyone. Today we", "start_ms": 0, "end_ms": 2000},
                {"text": "talk about resilience.", "start_ms": 2000, "end_ms": 4000},
            ],
            "ko_snippets": [
                {"text": "여러분 안녕하세요", "start_ms": 0, "end_ms": 1500},
            ],
        },
    )
    assert res.status_code == 202
    assert res.json()["segments"] == 2  # 문장 병합 적용

    segments = (
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
    assert [s.en_text for s in segments] == [
        "Hello everyone.",
        "Today we talk about resilience.",
    ]
    assert segments[0].ko_text == "여러분 안녕하세요"  # 시간 정렬 매칭

    job = (
        await db_session.execute(
            select(ExtractionJob).where(
                ExtractionJob.content_id == content.id, ExtractionJob.step == "transcript"
            )
        )
    ).scalar_one()
    assert job.status == "done"
    assert job.payload["source"] == "local_agent"

    await db_session.refresh(content)
    assert content.status == "pending"  # 번역/추출 재개 대기
    assert content.error_message is None

    # 세그먼트가 생겼으므로 대기 목록에서 사라진다
    listed = (await client.get("/api/agent/pending-transcripts", headers=AGENT_HEADERS)).json()
    assert listed["items"] == []

    # 중복 제출은 무시
    dup = await client.post(
        f"/api/agent/transcripts/{content.id}",
        headers=AGENT_HEADERS,
        json={"en_snippets": [{"text": "x.", "start_ms": 0, "end_ms": 1}]},
    )
    assert dup.json().get("skipped") is True


def test_agent_poll_filter_drops_polling_access_logs():
    """폴링 액세스 로그만 걸러내고 나머지는 통과 (진단 가시성)."""
    import logging

    from app.main import AgentPollFilter

    f = AgentPollFilter()

    def record(msg):
        return logging.LogRecord("uvicorn.access", logging.INFO, "", 0, msg, None, None)

    assert f.filter(record('"GET /api/agent/pending-transcripts HTTP/1.1" 200')) is False
    assert f.filter(record('"GET /api/study/queue HTTP/1.1" 200')) is True
