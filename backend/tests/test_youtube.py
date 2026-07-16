"""유튜브 파싱/문장 병합 (docs/specs/content-pipeline.md 단계 1-2)."""

from app.services.youtube import Snippet, merge_into_sentences, parse_video_id


def test_parse_video_id_supported_formats():
    cases = {
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ": "dQw4w9WgXcQ",
        "https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ": "dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=10": "dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ": "dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ": "dQw4w9WgXcQ",
    }
    for url, expected in cases.items():
        assert parse_video_id(url) == expected, url


def test_parse_video_id_rejects_invalid():
    assert parse_video_id("https://example.com/watch?v=abc") is None
    assert parse_video_id("not a url") is None


def test_merge_into_sentences_joins_across_snippets():
    snippets = [
        Snippet("Hello everyone. Today we", 0, 2000),
        Snippet("talk about resilience.", 2000, 4000),
        Snippet("Let's start!", 4000, 6000),
    ]
    merged = merge_into_sentences(snippets)
    assert [s.text for s in merged] == [
        "Hello everyone.",
        "Today we talk about resilience.",
        "Let's start!",
    ]
    # 두 번째 문장은 1번 조각 중간에서 시작(문자 비례 보간)해 2번 조각에서 끝난다
    assert 0 < merged[1].start_ms < 2000
    assert merged[1].end_ms == 4000


def test_merge_interpolates_within_shared_snippet_no_overlap():
    """한 조각에 여러 문장이 걸치면 문자 비례로 시각 배분 — 구간 겹침 금지.

    조각 시작/끝을 그대로 쓰면 문장 구간이 3~5초씩 겹쳐 재생 문장 표시가
    음성보다 늦어진다 (2026-07-16 라이브러리 딜레이 실측 데이터 근거).
    """
    snippets = [
        Snippet("First sentence. Second one", 0, 4000),
        Snippet("continues here.", 4000, 6000),
    ]
    merged = merge_into_sentences(snippets)
    assert [s.text for s in merged] == ["First sentence.", "Second one continues here."]
    first, second = merged
    assert first.start_ms == 0
    assert first.end_ms <= second.start_ms  # 겹침 없음
    assert 1000 <= first.end_ms <= 3000  # "First sentence." ≈ 조각의 중간 지점
    assert second.end_ms == 6000

    # 전체 문장 구간은 항상 단조 증가 (표시 매칭이 첫 일치를 골라도 안전)
    for prev, nxt in zip(merged, merged[1:], strict=False):
        assert prev.end_ms <= nxt.start_ms


def test_merge_keeps_snippets_when_no_punctuation():
    """자동 생성 자막(문장부호 없음)은 조각 그대로."""
    snippets = [Snippet("hello everyone today", 0, 2000), Snippet("we talk about", 2000, 4000)]
    assert merge_into_sentences(snippets) == snippets


def test_transcript_api_uses_proxy_when_configured(monkeypatch):
    """프록시 env 설정 시 GenericProxyConfig 로 생성 (docs/specs/content-pipeline.md)."""
    from app.core.config import get_settings
    from app.services.youtube import _transcript_api

    monkeypatch.setenv("YT_PROXY_URL", "http://user:pass@proxy.example:8080")
    get_settings.cache_clear()
    try:
        api = _transcript_api()
        assert api is not None  # 프록시 설정으로도 생성 성공 (내부 구조 비의존)
    finally:
        monkeypatch.delenv("YT_PROXY_URL")
        get_settings.cache_clear()


def test_blocked_error_converted_to_friendly_message(monkeypatch):
    from app.services import youtube

    class RequestBlocked(Exception):
        pass

    class FakeApi:
        def list(self, video_id):
            raise RequestBlocked("cloud ip blocked")

    monkeypatch.setattr(youtube, "_transcript_api", lambda: FakeApi())
    try:
        youtube.fetch_transcript("abc123def45")
        raise AssertionError("should have raised")
    except youtube.TranscriptNotFoundError as exc:
        assert "차단" in str(exc)
        assert "수기 입력" in str(exc)
        assert len(str(exc)) < 200  # 라이브러리 장문 메시지 노출 금지


async def test_fetch_license_parses_and_skips_without_key(monkeypatch):
    """Data API 응답의 status.license 파싱, 키 미설정이면 네트워크 없이 None."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.core.config import get_settings
    from app.services import youtube

    settings = get_settings()
    original = settings.youtube_api_key
    try:
        settings.youtube_api_key = ""
        assert await youtube.fetch_license("abc123def45") is None  # 키 없음 → 스킵

        settings.youtube_api_key = "test-key"
        res = MagicMock()
        res.json.return_value = {"items": [{"status": {"license": "creativeCommons"}}]}
        res.raise_for_status.return_value = None
        http = MagicMock()
        http.__aenter__ = AsyncMock(return_value=http)
        http.__aexit__ = AsyncMock(return_value=False)
        http.get = AsyncMock(return_value=res)
        with patch.object(youtube.httpx, "AsyncClient", return_value=http):
            assert await youtube.fetch_license("abc123def45") == "creativeCommons"

        # 조회 실패는 None (게이트가 안전 기본값으로 차단)
        http.get = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(youtube.httpx, "AsyncClient", return_value=http):
            assert await youtube.fetch_license("abc123def45") is None
    finally:
        settings.youtube_api_key = original
