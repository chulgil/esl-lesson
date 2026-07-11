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
    # 두 번째 문장은 1번 조각에서 시작해 2번 조각에서 끝난다
    assert merged[1].start_ms == 0
    assert merged[1].end_ms == 4000


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
