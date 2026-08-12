"""신경망 TTS 캐시 — 발음 오디오 (services/tts.py, 2026-08-05 음성 품질 보고)."""

from tests.test_study import login


async def test_tts_generates_then_serves_from_cache(client, db_session, monkeypatch):
    from app.services import tts as tts_service

    calls: list[tuple[str, str]] = []

    async def fake_synth(text, voice):
        calls.append((text, voice))
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

    async def boom(text, voice):
        raise RuntimeError("edge down")

    monkeypatch.setattr(tts_service, "synthesize", boom)
    await login(client, db_session)
    res = await client.get("/api/tts", params={"text": "word"})
    assert res.status_code == 502  # 프론트가 브라우저 TTS 로 폴백


async def test_tts_validates_length(client, db_session):
    await login(client, db_session)
    assert (await client.get("/api/tts", params={"text": "x" * 121})).status_code == 422


# --- 다국어 (docs/specs/chat-translation.md) --------------------------------------


async def test_tts_lang_selects_voice_and_caches_separately(client, db_session, monkeypatch):
    from app.services import tts as tts_service

    calls: list[tuple[str, str]] = []

    async def fake_synth(text, voice):
        calls.append((text, voice))
        return f"AUDIO:{voice}".encode()

    monkeypatch.setattr(tts_service, "synthesize", fake_synth)
    await login(client, db_session)

    en = await client.get("/api/tts", params={"text": "hello", "lang": "en"})
    ko = await client.get("/api/tts", params={"text": "hello", "lang": "ko"})
    ja = await client.get("/api/tts", params={"text": "hello", "lang": "ja"})
    assert en.status_code == ko.status_code == ja.status_code == 200
    # 언어별로 다른 보이스가 쓰였고, 캐시 키가 분리돼 3회 모두 새로 합성됨
    assert {v for _, v in calls} == {
        tts_service.TTS_VOICES["en"],
        tts_service.TTS_VOICES["ko"],
        tts_service.TTS_VOICES["ja"],
    }
    assert len(calls) == 3

    # 같은 lang 재요청은 캐시 히트
    again = await client.get("/api/tts", params={"text": "hello", "lang": "en"})
    assert again.content == en.content
    assert len(calls) == 3


async def test_tts_defaults_to_english_voice(client, db_session, monkeypatch):
    from app.services import tts as tts_service

    calls: list[str] = []

    async def fake_synth(text, voice):
        calls.append(voice)
        return b"FAKEMP3"

    monkeypatch.setattr(tts_service, "synthesize", fake_synth)
    await login(client, db_session)

    await client.get("/api/tts", params={"text": "no lang param"})
    assert calls == [tts_service.TTS_VOICES["en"]]


async def test_tts_rejects_unsupported_lang(client, db_session):
    await login(client, db_session)
    res = await client.get("/api/tts", params={"text": "hello", "lang": "fr"})
    assert res.status_code == 422
