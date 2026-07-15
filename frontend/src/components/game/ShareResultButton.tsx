"use client";

import { useState } from "react";
import { type ShareCardData, shareResultImage } from "@/lib/share-image";

/** 게임 결과 공유 버튼 — 모바일=공유 시트(카톡), 데스크톱=이미지 저장 (P3) */
export function ShareResultButton({ data }: { data: ShareCardData }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleShare() {
    setBusy(true);
    setMessage(null);
    try {
      const outcome = await shareResultImage(data);
      if (outcome === "downloaded") {
        setMessage("이미지를 저장했어요 — 카톡에 첨부해서 자랑해보세요!");
      }
    } catch {
      setMessage("이미지 생성에 실패했어요.");
    }
    setBusy(false);
  }

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        disabled={busy}
        onClick={handleShare}
        className="flex min-h-11 cursor-pointer items-center gap-2 rounded-md border-2 border-ink/20 bg-white px-4 text-sm font-bold transition hover:border-ink/50 disabled:opacity-50"
      >
        <svg
          viewBox="0 0 24 24"
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M4 12v8a1 1 0 001 1h14a1 1 0 001-1v-8M16 6l-4-4-4 4m4-4v13" />
        </svg>
        결과 공유
      </button>
      {message && <p className="text-xs opacity-60">{message}</p>}
    </div>
  );
}
