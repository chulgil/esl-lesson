"use client";

import { useEffect, useState } from "react";

const OPEN_EVENT = "esl-open-video";

/** 채팅 유튜브 링크 — 앱 안 임베드 플레이어 (2026-08-12).
 *
 *  모바일에서 youtube.com 링크를 새 탭으로 열면 OS 앱 링크가 가로채
 *  유튜브 앱으로 이동한다(2026-08-12 보고). 임베드 iframe 은 앱 가로채기가
 *  없어 브라우저(우리 앱) 안에서 바로 재생된다 — 학습 동선도 안 끊긴다.
 *  ImageLightbox 와 같은 전역 1개 마운트(layout.tsx)·같은 탈출 동선. */
export function openVideo(videoId: string): void {
  window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: videoId }));
}

export function VideoLightbox() {
  const [videoId, setVideoId] = useState<string | null>(null);

  useEffect(() => {
    const onOpen = (e: Event) => setVideoId((e as CustomEvent<string>).detail);
    window.addEventListener(OPEN_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_EVENT, onOpen);
  }, []);

  useEffect(() => {
    if (videoId === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setVideoId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [videoId]);

  // 뒤 화면 스크롤 잠금 — ImageLightbox 와 동일
  useEffect(() => {
    if (videoId === null) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [videoId]);

  if (videoId === null) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="동영상 보기"
      onClick={() => setVideoId(null)}
      className="fixed inset-0 z-[70] flex h-[100dvh] w-full items-center justify-center bg-ink/80 p-2 sm:p-6"
    >
      <button
        type="button"
        onClick={() => setVideoId(null)}
        aria-label="닫기 (Esc)"
        className="absolute top-3 right-3 flex min-h-11 min-w-11 items-center justify-center rounded-full bg-ink/60 text-xl leading-none text-white"
      >
        ×
      </button>
      {/* 플레이어 클릭은 재생 조작 — 닫힘 버블링 차단. 바깥 배경만 닫기 */}
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-3xl overflow-hidden rounded-lg bg-black shadow-2xl"
      >
        <div className="aspect-video w-full">
          <iframe
            src={`https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&rel=0`}
            title="YouTube 동영상"
            allow="autoplay; encrypted-media; picture-in-picture"
            allowFullScreen
            className="h-full w-full border-0"
          />
        </div>
      </div>
    </div>
  );
}
