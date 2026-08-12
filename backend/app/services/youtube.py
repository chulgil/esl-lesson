"""유튜브 메타데이터/자막 추출 (docs/specs/content-pipeline.md 단계 1-2)."""

import re
from dataclasses import dataclass

import httpx

from app.services.langs import SUPPORTED_LANGS

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
    """Data API 로 라이선스 조회 — 'creativeCommon' | 'youtube' | None(키 없음/실패).

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


def detect_video_lang(raw_lang: str | None) -> str | None:
    """defaultAudioLanguage/defaultLanguage 원본 코드를 지원 언어(ko/en/ja)로 매핑.

    미표기·지원 밖 언어(langs.SUPPORTED_LANGS 밖)는 None — 등록 화면 값으로 폴백
    (docs/specs/chat-translation.md 콘텐츠 다국어).
    """
    if not raw_lang:
        return None
    lowered = raw_lang.lower()
    for code in SUPPORTED_LANGS:
        if lowered.startswith(code):
            return code
    return None


async def fetch_video_lang(video_id: str) -> str | None:
    """Data API 로 defaultAudioLanguage(없으면 defaultLanguage) 조회 → 지원 언어 매핑.

    등록 화면에서 lang 자동 감지용. 키 없음/조회 실패/미지원 언어는 None
    (호출부가 body 에 명시된 값으로 폴백).
    """
    from app.core.config import get_settings

    api_key = get_settings().youtube_api_key
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                DATA_API_VIDEOS_URL,
                params={"part": "snippet", "id": video_id, "key": api_key},
            )
            res.raise_for_status()
            items = res.json().get("items", [])
        if not items:
            return None
        snippet = items[0].get("snippet", {})
        raw_lang = snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage")
        return detect_video_lang(raw_lang)
    except Exception:
        return None


DATA_API_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def is_language_ok(lang: str | None, language: str = "en") -> bool:
    """언어 메타 판정 — 명시적 비대상 언어만 제외.

    defaultAudioLanguage/defaultLanguage 는 업로더 설정이라 미표기가 흔하다 —
    미표기(None/"")는 통과시키고, ko/ja 등 명시적 타언어만 거른다. 전부
    엄격 차단하면 메타 없는 영어 영상까지 사라져 결과가 텅 빈다.
    """
    if not lang:
        return True
    return lang.lower().startswith(language)


async def search_cc_videos(
    query: str,
    page_token: str | None = None,
    max_results: int = 50,
    language: str = "en",
) -> dict | None:
    """Data API 검색 — CC(creativeCommon) + 자막 보유 + 학습 언어(영어) 영상만.

    백오피스 "CC 영상 찾기"용 (docs/specs/content-governance.md). None = API 키
    미설정. 반환: {"items": [...], "next_page_token": str|None}.

    - videoCaption=closedCaption: 자막 없는 영상 사전 제거 (파이프라인이 자막 전제)
    - relevanceLanguage 는 부스팅일 뿐 필터가 아니라 비영어가 섞였다 (2026-08-05
      보고) → regionCode + videos.list snippet 언어 메타로 명시적 비영어 후처리 제거
    - 결과가 적다·페이징이 없다 보고 → maxResults 50(API 최대) + pageToken 페이징
    - 쿼터: search.list 100 + videos.list 1 per 호출 — 관리자 전용이라 허용.
      등록 시 fetch_license 가 라이선스를 재확인하므로 검색 필터는 후보 제시용.
    """
    from app.core.config import get_settings

    api_key = get_settings().youtube_api_key
    if not api_key:
        return None
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoLicense": "creativeCommon",
        "videoCaption": "closedCaption",
        "relevanceLanguage": language,
        "regionCode": "US",
        "maxResults": max_results,
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(DATA_API_SEARCH_URL, params=params)
        res.raise_for_status()
        data = res.json()
        items = data.get("items", [])

        # 언어 메타 일괄 조회 — 명시적 비영어 제거 (videos.list 1 unit)
        ids = [i.get("id", {}).get("videoId") for i in items]
        ids = [v for v in ids if v]
        lang_of: dict[str, str | None] = {}
        if ids:
            vres = await client.get(
                DATA_API_VIDEOS_URL,
                params={"part": "snippet", "id": ",".join(ids), "key": api_key},
            )
            vres.raise_for_status()
            for v in vres.json().get("items", []):
                sn = v.get("snippet", {})
                lang_of[v.get("id", "")] = sn.get("defaultAudioLanguage") or sn.get(
                    "defaultLanguage"
                )

    results = []
    for item in items:
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id or not is_language_ok(lang_of.get(video_id), language):
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
    return {"items": results, "next_page_token": data.get("nextPageToken")}


CREDIT_LABELS = ("translator:", "reviewer:", "transcriber:")
# 이름에 끼는 소문자 전치사(카운트 제외) — "Peter van de Ven" 류
NAME_PARTICLES = {"van", "de", "der", "von", "da", "del", "la", "le", "di", "den"}


def strip_caption_credits(text: str) -> str:
    """자막 선두의 TED 크레딧("Translator: 이름 Reviewer: 이름") 제거.

    자막 첫 큐에 크레딧이 발화와 병합되어 들어와 학습 텍스트를 오염시켰다
    (2026-08-05 콘텐츠 검증 — content 7 실측). 이름은 "이름+성" 2토큰(전치사
    카운트 제외)으로 보고, 문장부호가 붙은 토큰(발화 시작)에서 멈춘다 —
    상한을 늘리면 대문자로 시작하는 발화 첫 단어까지 삼킨다.
    """
    tokens = text.split()
    i = 0
    while i < len(tokens) and tokens[i].lower() in CREDIT_LABELS:
        i += 1
        counted = 0
        while i < len(tokens) and counted < 2:
            token = tokens[i]
            if tokens[i].lower() in CREDIT_LABELS:
                break  # 다음 크레딧 라벨 — 바깥 루프가 처리
            if any(p in token for p in ",.!?"):
                break  # 문장부호 = 발화 시작
            if token.lower() in NAME_PARTICLES:
                i += 1
                continue  # 전치사는 카운트 없이 소비
            if token[0].isupper():
                i += 1
                counted += 1
                continue
            break
    if i == 0:
        return text
    return " ".join(tokens[i:])


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
