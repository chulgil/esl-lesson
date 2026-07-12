"use client";

import { useEffect, useRef, useState } from "react";

/** 유튜브 구간 재생 (A-B 루프) — 학습 중 "구간 듣기" (docs/specs/learning.md)
 *  버튼을 눌러야 플레이어가 열린다 (자동재생 스포일러 방지 + 대역폭 절약).
 */

export interface MediaSegment {
  video_id: string;
  start_ms: number;
  end_ms: number;
}

export function SegmentPlayer({
  media,
  label = "출처 구간 듣기",
}: {
  media: MediaSegment;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const [loop, setLoop] = useState(false);
  const holderRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<YTPlayer | null>(null);
  const loopRef = useRef(false);
  loopRef.current = loop;

  const start = media.start_ms / 1000;
  // 자동 자막의 end_ms 가 문장 범위를 넘길 수 있어 상한(8초)으로 제한 (2026-07-11 피드백)
  const rawEnd = media.end_ms / 1000;
  const end = Math.min(rawEnd, start + 8);

  useEffect(() => {
    if (!open || !holderRef.current) return;

    let cancelled = false;

    function create() {
      if (cancelled || !holderRef.current) return;
      playerRef.current = new window.YT!.Player(holderRef.current, {
        videoId: media.video_id,
        playerVars: { rel: 0, start: Math.floor(start) },
        events: {
          onReady: (event: { target: YTPlayer }) => {
            event.target.seekTo(start, true);
            event.target.playVideo();
          },
        },
      });
    }

    if (window.YT?.Player) {
      create();
    } else {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        prev?.();
        create();
      };
      if (!document.querySelector("script[src*='iframe_api']")) {
        const script = document.createElement("script");
        script.src = "https://www.youtube.com/iframe_api";
        document.head.appendChild(script);
      }
    }

    const timer = setInterval(() => {
      const player = playerRef.current;
      if (!player) return;
      try {
        if (player.getCurrentTime() >= end) {
          if (loopRef.current) {
            player.seekTo(start, true);
          } else {
            player.pauseVideo();
          }
        }
      } catch {
        // 초기화 전 호출 무시
      }
    }, 250);

    return () => {
      cancelled = true;
      clearInterval(timer);
      try {
        playerRef.current?.destroy?.();
      } catch {
        // 이미 제거된 경우 무시
      }
      playerRef.current = null;
    };
  }, [open, media.video_id, start, end]);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex min-h-11 items-center gap-2 rounded-md border-2 border-brick-blue/50 bg-white px-4 text-sm font-bold text-brick-blue transition hover:-translate-y-0.5 hover:border-brick-blue"
      >
        <SpeakerIcon />
        {label}
      </button>
    );
  }

  return (
    <div className="w-full max-w-sm">
      <div className="aspect-video overflow-hidden rounded-lg border-2 border-ink/15 bg-black">
        <div ref={holderRef} className="h-full w-full" />
      </div>
      <div className="mt-2 flex items-center gap-4 text-sm">
        <button
          type="button"
          onClick={() => {
            playerRef.current?.seekTo(start, true);
            playerRef.current?.playVideo();
          }}
          className="font-bold text-brick-blue hover:underline"
        >
          다시 듣기
        </button>
        <label className="flex cursor-pointer items-center gap-1.5">
          <input
            type="checkbox"
            checked={loop}
            onChange={(e) => setLoop(e.target.checked)}
          />
          구간 반복
        </label>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="ml-auto opacity-60 hover:underline"
        >
          닫기
        </button>
      </div>
    </div>
  );
}

function SpeakerIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M11 5 6 9H2v6h4l5 4V5Z" />
      <path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13" />
    </svg>
  );
}
