"""신경망 TTS 캐시 — 발음 오디오 (services/tts.py, 2026-08-05 음성 품질 보고)."""

from tests.test_study import login


async def test_tts_generates_then_serves_from_cache(client, db_session, monkeypatch):
    from app.services import tts as tts_service

    calls: list[str] = []

    async def fake_synth(text):
        calls.append(text)
        return b"FAKEMP3"

    monkeypatch.setattr(tts_service, "synthesize", fake_synth)
    await login(client, db_session)

    res = await client.get("/api/tts", params={"text": "Serendipity"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert res.content == b"FAKEMP3"

    # 대소문자만 다른 재요청 — 캐시 히트 (합성 1회만)
    res = await client.get("/api/tts", params={"text": "serendipity"})
    assert res.status_code == 200 and res.content == b"FAKEMP3"
    assert len(calls) == 1


async def test_tts_failure_returns_502_for_browser_fallback(client, db_session, monkeypatch):
    from app.services import tts as tts_service

    async def boom(text):
        raise RuntimeError("edge down")

    monkeypatch.setattr(tts_service, "synthesize", boom)
    await login(client, db_session)
    res = await client.get("/api/tts", params={"text": "word"})
    assert res.status_code == 502  # 프론트가 브라우저 TTS 로 폴백


async def test_tts_validates_length(client, db_session):
    await login(client, db_session)
    assert (await client.get("/api/tts", params={"text": "x" * 121})).status_code == 422
