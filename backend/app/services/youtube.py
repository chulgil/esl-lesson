"""유튜브 메타데이터/자막 추출 (docs/specs/content-pipeline.md 단계 1-2)."""

import re
from dataclasses import dataclass

import httpx

VIDEO_ID_PATTERNS = (
    re.compile(r"(?:youtube\.com/watch\?(?:.*&)?v=)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtu\.be/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})"),
)

OEMBED_URL = "https://www.youtube.com/oembed"

_SENTENCE_END = re.compile(r"(?<=[.?!])\s+")


class TranscriptNotFoundError(Exception):
    """영어 자막이 없는 영상 — 수기 입력 경로로 안내."""


def parse_video_id(url: str) -> str | None:
    for pattern in VIDEO_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


async def fetch_title(video_id: str) -> str:
    """oEmbed 로 제목 조회 (API 키 불필요)."""
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(
            OEMBED_URL,
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
        )
        res.raise_for_status()
        return res.json()["title"]


@dataclass
class Snippet:
    text: str
    start_ms: int
    end_ms: int


@dataclass
class TranscriptResult:
    language: str
    is_generated: bool
    snippets: list[Snippet]


BLOCKED_MESSAGE = (
    "유튜브가 서버 IP의 자막 요청을 차단했습니다. "
    "프록시 설정(WEBSHARE_PROXY_* 또는 YT_PROXY_URL) 후 재시도하거나, "
    "수기 입력으로 등록해주세요."
)


def _transcript_api():
    """프록시 설정이 있으면 프록시 경유 (클라우드 IP 차단 우회)."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

    from app.core.config import get_settings

    settings = get_settings()
    if settings.webshare_proxy_username and settings.webshare_proxy_password:
        return YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=settings.webshare_proxy_username,
                proxy_password=settings.webshare_proxy_password,
            )
        )
    if settings.yt_proxy_url:
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(
                http_url=settings.yt_proxy_url, https_url=settings.yt_proxy_url
            )
        )
    return YouTubeTranscriptApi()


def _is_blocked(exc: Exception) -> bool:
    return type(exc).__name__ in ("RequestBlocked", "IpBlocked")


def fetch_transcript(video_id: str, languages: tuple[str, ...] = ("en",)) -> TranscriptResult:
    """youtube-transcript-api 로 자막 추출. 수동 자막 우선 (동기 — 워커 스레드에서 호출)."""
    api = _transcript_api()
    try:
        transcript_list = api.list(video_id)
    except Exception as exc:
        if _is_blocked(exc):
            raise TranscriptNotFoundError(BLOCKED_MESSAGE) from exc
        raise TranscriptNotFoundError(f"자막 조회 실패: {type(exc).__name__}") from exc

    transcript = None
    for finder in ("find_manually_created_transcript", "find_generated_transcript"):
        try:
            transcript = getattr(transcript_list, finder)(list(languages))
            break
        except Exception:
            continue
    if transcript is None:
        raise TranscriptNotFoundError(f"no {languages} transcript for {video_id}")

    try:
        fetched = transcript.fetch()
    except Exception as exc:
        if _is_blocked(exc):
            raise TranscriptNotFoundError(BLOCKED_MESSAGE) from exc
        raise
    snippets = [
        Snippet(
            text=s.text.replace("\n", " ").strip(),
            start_ms=int(s.start * 1000),
            end_ms=int((s.start + s.duration) * 1000),
        )
        for s in fetched
        if s.text.strip()
    ]
    return TranscriptResult(
        language=transcript.language_code,
        is_generated=transcript.is_generated,
        snippets=snippets,
    )


def merge_into_sentences(snippets: list[Snippet]) -> list[Snippet]:
    """자막 조각을 문장 단위로 병합. 문장부호 없는(자동 생성) 자막은 조각 그대로 반환."""
    if not snippets:
        return []

    full_parts: list[str] = []
    offsets: list[tuple[int, Snippet]] = []  # (누적 문자 오프셋, 원 조각)
    pos = 0
    for snip in snippets:
        offsets.append((pos, snip))
        full_parts.append(snip.text)
        pos += len(snip.text) + 1
    full_text = " ".join(full_parts)

    if not re.search(r"[.?!]", full_text):
        return snippets

    sentences: list[Snippet] = []
    cursor = 0
    for raw in _SENTENCE_END.split(full_text):
        sentence = raw.strip()
        if not sentence:
            continue
        start_off = full_text.find(sentence, cursor)
        cursor = start_off + len(sentence)
        end_off = cursor
        first = _snippet_at(offsets, start_off)
        last = _snippet_at(offsets, max(start_off, end_off - 1))
        sentences.append(Snippet(text=sentence, start_ms=first.start_ms, end_ms=last.end_ms))
    return sentences


def _snippet_at(offsets: list[tuple[int, Snippet]], char_offset: int) -> Snippet:
    current = offsets[0][1]
    for off, snip in offsets:
        if off > char_offset:
            break
        current = snip
    return current
