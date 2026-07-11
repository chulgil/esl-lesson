"""로컬 자막 수집기 — 집 IP로 유튜브 자막을 대신 가져와 서버에 제출한다.

서버(클라우드 IP)는 유튜브에 차단되므로, 이 스크립트를 로컬 맥/PC에서 돌리면
"자막 준비 중" 콘텐츠가 자동으로 처리된다. AI 불필요 — 가벼운 HTTP 호출만.

사용법 (backend/ 디렉토리에서):
    ESL_AGENT_TOKEN=<토큰> uv run python scripts/transcript_agent.py           # 30초 간격 상시 루프
    ESL_AGENT_TOKEN=<토큰> uv run python scripts/transcript_agent.py --once    # 1회 처리 후 종료

환경변수:
    ESL_SERVER       기본 https://esladmin.lessonaza.app
    ESL_AGENT_TOKEN  서버 .env.api 의 AGENT_TOKEN 과 동일 값 (필수)
"""

import os
import sys
import time

import httpx

SERVER = os.environ.get("ESL_SERVER", "https://esladmin.lessonaza.app").rstrip("/")
TOKEN = os.environ.get("ESL_AGENT_TOKEN", "")
POLL_SECONDS = 30


def fetch_snippets(video_id: str, languages: tuple[str, ...]) -> list[dict] | None:
    """로컬 IP 로 자막 조회. 없으면 None."""
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.list(video_id)
    except Exception as exc:
        print(f"  [x] {video_id}: 자막 목록 조회 실패 ({type(exc).__name__})")
        return None
    transcript = None
    for finder in ("find_manually_created_transcript", "find_generated_transcript"):
        try:
            transcript = getattr(transcript_list, finder)(list(languages))
            break
        except Exception:
            continue
    if transcript is None:
        return None
    return [
        {
            "text": s.text.replace("\n", " ").strip(),
            "start_ms": int(s.start * 1000),
            "end_ms": int((s.start + s.duration) * 1000),
        }
        for s in transcript.fetch()
        if s.text.strip()
    ]


def process_once(client: httpx.Client) -> int:
    res = client.get(f"{SERVER}/api/agent/pending-transcripts")
    res.raise_for_status()
    items = res.json()["items"]
    if not items:
        return 0
    print(f"대기 {len(items)}건 발견")
    done = 0
    for item in items:
        video_id = item["youtube_video_id"]
        en = fetch_snippets(video_id, ("en",))
        if not en:
            print(f"  [x] {video_id}: 영어 자막 없음/실패 — 건너뜀")
            continue
        ko = fetch_snippets(video_id, ("ko",)) or []
        submit = client.post(
            f"{SERVER}/api/agent/transcripts/{item['content_id']}",
            json={"en_snippets": en, "ko_snippets": ko},
        )
        if submit.status_code == 202:
            print(f"  [o] {video_id}: 제출 완료 (en {len(en)}조각, ko {len(ko)}조각)")
            done += 1
        else:
            print(f"  [x] {video_id}: 제출 실패 {submit.status_code} {submit.text[:100]}")
    return done


def main() -> None:
    if not TOKEN:
        print("ESL_AGENT_TOKEN 환경변수가 필요합니다.")
        sys.exit(1)
    once = "--once" in sys.argv
    client = httpx.Client(timeout=30, headers={"X-Agent-Token": TOKEN})
    print(f"자막 수집기 시작 — 서버 {SERVER} ({'1회' if once else f'{POLL_SECONDS}초 간격'})")
    while True:
        try:
            processed = process_once(client)
            if processed:
                print(f"{processed}건 처리 완료 — 서버가 번역/추출을 이어서 진행합니다")
        except Exception as exc:
            print(f"[!] 오류: {type(exc).__name__}: {exc}")
        if once:
            break
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
