"use client";

import Link from "next/link";
import { BackLink } from "@/components/nav/BackLink";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { studyApi, type LibraryDetail } from "@/lib/study-api";

/** 라이브러리 상세 — 전문(全文) 나열 대신 재생 중 문장만 동기 표시.
 *  전체 스크립트 노출은 저작권 리스크 상위라 제거 (2026-07-14 저작권 검토). */
export default function LibraryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<LibraryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentSeq, setCurrentSeq] = useState<number | null>(null);
  const [loop, setLoop] = useState(false);

  const playerRef = useRef<YTPlayer | null>(null);
  const rangeRef = useRef<{ start: number; end: number } | null>(null);
  const loopRef = useRef(false);
  const detailRef = useRef<LibraryDetail | null>(null);
  loopRef.current = loop;
  detailRef.current = detail;

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

  // 재생 감시: 현재 구간 자막 동기 + A-B 루프 (docs/specs/learning.md)
  useEffect(() => {
    const timer = setInterval(() => {
      const player = playerRef.current;
      if (!player) return;
      try {
        const now = player.getCurrentTime() * 1000;

        const segments = detailRef.current?.segments ?? [];
        const active = segments.find(
          (s) =>
            s.start_ms != null &&
            now >= s.start_ms &&
            now < (s.end_ms ?? s.start_ms + 5000),
        );
        setCurrentSeq(active ? active.seq : null);

        const range = rangeRef.current;
        if (range && now >= range.end * 1000) {
          if (loopRef.current) {
            player.seekTo(range.start, true);
          } else {
            player.pauseVideo();
            rangeRef.current = null;
          }
        }
      } catch {
        // 플레이어 미초기화 등은 무시
      }
    }, 250);
    return () => clearInterval(timer);
  }, []);

  const playSegment = useCallback(
    (startMs: number | null, endMs: number | null) => {
      const player = playerRef.current;
      if (!player || startMs == null) return;
      rangeRef.current = {
        start: startMs / 1000,
        end: (endMs ?? startMs + 5000) / 1000,
      };
      player.seekTo(startMs / 1000, true);
      player.playVideo();
    },
    [],
  );

  function step(direction: -1 | 1) {
    const segments = detail?.segments ?? [];
    const playable = segments.filter((s) => s.start_ms != null);
    if (playable.length === 0) return;
    const idx = playable.findIndex((s) => s.seq === currentSeq);
    const next =
      idx === -1
        ? playable[0]
        : playable[Math.min(playable.length - 1, Math.max(0, idx + direction))];
    playSegment(next.start_ms, next.end_ms);
  }

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
  const current = detail.segments.find((s) => s.seq === currentSeq) ?? null;

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex flex-wrap items-center gap-4">
        <BackLink href="/library" label="라이브러리" />
        <h1 className="font-hand text-2xl font-bold">
          <span className="hl">{detail.title}</span>
        </h1>
      </header>

      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        {hasPlayer ? (
          <>
            <div className="aspect-video overflow-hidden rounded-lg border-2 border-ink/10 bg-black">
              <div id="yt-player" className="h-full w-full" />
            </div>

            {/* 현재 문장 — 재생과 동기화, 전문은 표시하지 않음 */}
            <div className="min-h-28 rounded-lg border-2 border-ink/10 bg-white p-5 text-center">
              {current ? (
                <>
                  <p className="text-lg font-medium">{current.en_text}</p>
                  {current.ko_text && (
                    <p className="mt-1 text-sm opacity-60">{current.ko_text}</p>
                  )}
                </>
              ) : (
                <p className="py-4 text-sm opacity-40">
                  영상을 재생하면 지금 나오는 문장이 여기 표시돼요
                </p>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => step(-1)}
                className="min-h-11 rounded-md border-2 border-ink/25 bg-white px-4 font-bold shadow-sm transition hover:border-brick-blue"
              >
                ← 이전 문장
              </button>
              <button
                type="button"
                onClick={() => step(1)}
                className="min-h-11 rounded-md border-2 border-ink/25 bg-white px-4 font-bold shadow-sm transition hover:border-brick-blue"
              >
                다음 문장 →
              </button>
              <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-md border-2 border-ink/15 bg-white px-3 text-sm">
                <input
                  type="checkbox"
                  checked={loop}
                  onChange={(e) => setLoop(e.target.checked)}
                />
                이 문장 반복 (A-B 루프)
              </label>
            </div>

            <p className="text-center text-xs opacity-50">
              원저작자 보호를 위해 전체 스크립트는 제공하지 않아요 — 문장별
              학습은 [오늘의 학습]에서 이어져요 ·{" "}
              <Link href="/copyright" className="underline underline-offset-2">
                저작권 안내
              </Link>
            </p>
          </>
        ) : (
          <p className="text-sm opacity-60">
            이 콘텐츠는 재생할 영상이 없어요. 추출된 표현은 [오늘의 학습] 큐에서
            만나요.
          </p>
        )}
      </div>
    </main>
  );
}
