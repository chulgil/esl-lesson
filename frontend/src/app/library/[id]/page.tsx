"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { studyApi, type LibraryDetail } from "@/lib/study-api";

/** YouTube IFrame Player 최소 타입 */
interface YTPlayer {
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  playVideo(): void;
  pauseVideo(): void;
  getCurrentTime(): number;
}

declare global {
  interface Window {
    YT?: { Player: new (el: string, opts: object) => YTPlayer };
    onYouTubeIframeAPIReady?: () => void;
  }
}

export default function LibraryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<LibraryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeSeq, setActiveSeq] = useState<number | null>(null);
  const [loop, setLoop] = useState(false);

  const playerRef = useRef<YTPlayer | null>(null);
  const rangeRef = useRef<{ start: number; end: number } | null>(null);
  const loopRef = useRef(false);
  loopRef.current = loop;

  useEffect(() => {
    studyApi
      .libraryDetail(Number(id))
      .then(setDetail)
      .catch((e) => setError(e.message));
  }, [id]);

  // YouTube IFrame API 로드 + 플레이어 생성
  useEffect(() => {
    if (!detail?.youtube_video_id) return;

    function createPlayer() {
      playerRef.current = new window.YT!.Player("yt-player", {
        videoId: detail!.youtube_video_id,
        playerVars: { rel: 0 },
      });
    }

    if (window.YT?.Player) {
      createPlayer();
    } else {
      window.onYouTubeIframeAPIReady = createPlayer;
      if (!document.querySelector("script[src*='iframe_api']")) {
        const script = document.createElement("script");
        script.src = "https://www.youtube.com/iframe_api";
        document.head.appendChild(script);
      }
    }
    return () => {
      playerRef.current = null;
    };
  }, [detail]);

  // 구간 감시: end 도달 시 반복(seek) 또는 정지 (docs/specs/learning.md A-B 루프)
  useEffect(() => {
    const timer = setInterval(() => {
      const player = playerRef.current;
      const range = rangeRef.current;
      if (!player || !range) return;
      try {
        const current = player.getCurrentTime();
        if (current >= range.end) {
          if (loopRef.current) {
            player.seekTo(range.start, true);
          } else {
            player.pauseVideo();
            rangeRef.current = null;
            setActiveSeq(null);
          }
        }
      } catch {
        // 플레이어 미초기화 등은 무시
      }
    }, 250);
    return () => clearInterval(timer);
  }, []);

  const playSegment = useCallback(
    (seq: number, startMs: number | null, endMs: number | null) => {
      const player = playerRef.current;
      if (!player || startMs == null) return;
      rangeRef.current = {
        start: startMs / 1000,
        end: (endMs ?? startMs + 5000) / 1000,
      };
      setActiveSeq(seq);
      player.seekTo(startMs / 1000, true);
      player.playVideo();
    },
    [],
  );

  if (error) {
    return (
      <main className="p-8">
        <p className="text-sm text-brick-red">{error}</p>
      </main>
    );
  }
  if (!detail) {
    return (
      <main className="p-8">
        <p className="text-sm opacity-60">불러오는 중...</p>
      </main>
    );
  }

  const hasPlayer = Boolean(detail.youtube_video_id);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex flex-wrap items-center gap-4">
        <Link href="/library" className="text-sm opacity-60 hover:underline">
          &lt; 라이브러리
        </Link>
        <h1 className="font-hand text-2xl font-bold">
          <span className="hl">{detail.title}</span>
        </h1>
        {hasPlayer && (
          <label className="ml-auto flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={loop}
              onChange={(e) => setLoop(e.target.checked)}
            />
            구간 반복 (A-B 루프)
          </label>
        )}
      </header>

      <div className="flex flex-col gap-6 lg:flex-row">
        {hasPlayer && (
          <div className="lg:sticky lg:top-4 lg:h-fit lg:w-[420px] lg:shrink-0">
            <div className="aspect-video overflow-hidden rounded-lg border-2 border-ink/10 bg-black">
              <div id="yt-player" className="h-full w-full" />
            </div>
            <p className="mt-2 text-xs opacity-50">
              문장을 클릭하면 해당 구간이 재생됩니다. 구간 반복을 켜면 계속
              반복돼요.
            </p>
          </div>
        )}

        <ul className="flex-1">
          {detail.segments.map((segment) => (
            <li
              key={segment.seq}
              className={`border-b border-ink/10 transition-colors ${
                activeSeq === segment.seq ? "bg-highlight/40" : ""
              }`}
            >
              <button
                type="button"
                disabled={!hasPlayer || segment.start_ms == null}
                onClick={() =>
                  playSegment(segment.seq, segment.start_ms, segment.end_ms)
                }
                className="w-full px-2 py-2 text-left disabled:cursor-default"
              >
                <span className="flex items-baseline gap-3">
                  {segment.start_ms != null && (
                    <span className="w-10 shrink-0 text-xs opacity-40">
                      {formatMs(segment.start_ms)}
                    </span>
                  )}
                  <span>
                    <span className="block">{segment.en_text}</span>
                    {segment.ko_text && (
                      <span className="block text-sm opacity-60">
                        {segment.ko_text}
                      </span>
                    )}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}

function formatMs(ms: number): string {
  const total = Math.floor(ms / 1000);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}
