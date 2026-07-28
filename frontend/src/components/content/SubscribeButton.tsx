"use client";

import { useEffect, useRef, useState } from "react";
import { myApi } from "@/lib/my-api";

const NOTICE_MS = 4000;

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
  const [notice, setNotice] = useState(false);
  const noticeTimer = useRef<number | null>(null);

  useEffect(() => {
    // 언마운트 후 setState 방지 — 안내 타이머 정리
    return () => {
      if (noticeTimer.current !== null)
        window.clearTimeout(noticeTimer.current);
    };
  }, []);

  async function toggle() {
    setBusy(true);
    setError(false);
    setNotice(false);
    const next = !on;
    try {
      if (next) {
        await myApi.subscribe(contentId);
      } else {
        await myApi.remove(contentId);
        // 빼기는 즉시 반영하되 "기록은 남는다"를 알려 상실감 없이 정리하게 한다
        setNotice(true);
        if (noticeTimer.current !== null)
          window.clearTimeout(noticeTimer.current);
        noticeTimer.current = window.setTimeout(
          () => setNotice(false),
          NOTICE_MS,
        );
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
    <span className="inline-flex flex-wrap items-center gap-2">
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
      {notice && (
        <span role="status" className="text-xs opacity-70">
          학습 기록은 안전하게 보관돼요 — 다시 담으면 그대로 이어져요
        </span>
      )}
    </span>
  );
}
