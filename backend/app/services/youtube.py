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


class TranscriptBlockedError(TranscriptNotFoundError):
    """유튜브가 서버 IP를 차단 — 로컬 수집기/프록시로 처리 가능."""


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


DATA_API_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


async def fetch_license(video_id: str) -> str | None:
    """Data API 로 라이선스 조회 — 'creativeCommons' | 'youtube' | None(키 없음/실패).

    공용 승격 CC 게이트용 (docs/specs/content-pipeline.md). 공식 API 라 약관 안전.
    """
    from app.core.config import get_settings

    api_key = get_settings().youtube_api_key
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                DATA_API_VIDEOS_URL,
                params={"part": "status", "id": video_id, "key": api_key},
            )
            res.raise_for_status()
            items = res.json().get("items", [])
        if not items:
            return None
        return items[0].get("status", {}).get("license")
    except Exception:
        # 조회 실패는 미확인(None) — 게이트가 안전 기본값으로 차단
        return None


DATA_API_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


async def search_cc_videos(query: str, max_results: int = 12) -> list[dict] | None:
    """Data API 검색 — CC(creativeCommon) + 자막 보유 영상만.

    백오피스 "CC 영상 찾기"용 (docs/specs/content-governance.md). None = API 키
    미설정. videoCaption=closedCaption 으로 자막 없는 영상을 사전에 거른다
    (파이프라인이 자막 전제). 등록 시 fetch_license 가 라이선스를 재확인하므로
    검색 필터는 후보 제시용이다. search.list 쿼터 100단위/호출 — 관리자 전용.
    """
    from app.core.config import get_settings

    api_key = get_settings().youtube_api_key
    if not api_key:
        return None
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(
            DATA_API_SEARCH_URL,
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "videoLicense": "creativeCommon",
                "videoCaption": "closedCaption",
                "relevanceLanguage": "en",
                "maxResults": max_results,
                "key": api_key,
            },
        )
        res.raise_for_status()
        items = res.json().get("items", [])
    results = []
    for item in items:
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id:
            continue
        results.append(
            {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "thumbnail_url": (snippet.get("thumbnails", {}).get("medium") or {}).get("url", ""),
            }
        )
    return results


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
            raise TranscriptBlockedError(BLOCKED_MESSAGE) from exc
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
            raise TranscriptBlockedError(BLOCKED_MESSAGE) from exc
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
        start_ms = _time_at(offsets, start_off)
        end_ms = max(start_ms, _time_at(offsets, end_off))
        sentences.append(Snippet(text=sentence, start_ms=start_ms, end_ms=end_ms))

    # 원본 조각끼리 겹치는 자막(2줄 롤링 표시)은 보간 후에도 조각 경계에서
    # 구간이 겹친다 — 시작은 단조 증가로, 이전 끝은 다음 시작까지로 자른다
    for prev, cur in zip(sentences, sentences[1:], strict=False):
        cur.start_ms = max(cur.start_ms, prev.start_ms)
        cur.end_ms = max(cur.end_ms, cur.start_ms)
        prev.end_ms = max(prev.start_ms, min(prev.end_ms, cur.start_ms))
    return sentences


def _time_at(offsets: list[tuple[int, Snippet]], char_offset: int) -> int:
    """전체 텍스트의 문자 위치 → 자막 시각 (조각 안 문자 비율 보간).

    조각 시작/끝을 그대로 쓰면 한 조각에 걸친 문장들이 조각 전체 구간을
    공유해 문장 구간이 3~5초씩 겹치고, 재생 문장 표시가 음성보다 늦어진다
    (2026-07-16 라이브러리 딜레이 실측). 보간으로 경계가 단조 증가한다.
    """
    base, snip = offsets[0]
    for off, s in offsets:
        if off > char_offset:
            break
        base, snip = off, s
    frac = (char_offset - base) / max(len(snip.text), 1)
    frac = min(max(frac, 0.0), 1.0)
    return round(snip.start_ms + (snip.end_ms - snip.start_ms) * frac)
