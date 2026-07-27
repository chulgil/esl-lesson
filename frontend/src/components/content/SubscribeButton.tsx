"use client";

import { useState } from "react";
import { myApi } from "@/lib/my-api";

/** 담기/빼기 토글 — 담은 콘텐츠만 오늘의 학습에 편입된다
 *  (docs/specs/content-governance.md 가시성 규칙). */
export function SubscribeButton({
  contentId,
  subscribed,
  onChange,
  size = "sm",
}: {
  contentId: number;
  subscribed: boolean;
  onChange?: (subscribed: boolean) => void;
  size?: "sm" | "md";
}) {
  const [on, setOn] = useState(subscribed);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function toggle() {
    setBusy(true);
    setError(false);
    const next = !on;
    try {
      if (next) {
        await myApi.subscribe(contentId);
      } else {
        await myApi.remove(contentId);
      }
      setOn(next);
      onChange?.(next);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  const height = size === "md" ? "min-h-11" : "min-h-9";
  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        disabled={busy}
        onClick={toggle}
        aria-pressed={on}
        className={`${height} cursor-pointer rounded-md border-2 px-3 text-sm font-bold transition disabled:opacity-50 ${
          on
            ? "border-ink/20 bg-white opacity-70 hover:border-ink/40"
            : "border-brick-green/60 bg-white text-brick-green hover:-translate-y-0.5 hover:border-brick-green"
        }`}
      >
        {busy ? "..." : on ? "담김 — 빼기" : "+ 내 학습에 담기"}
      </button>
      {error && <span className="text-xs text-brick-red">잠시 후 다시</span>}
    </span>
  );
}
