"use client";

import { useEffect, useRef, useState } from "react";
import { KAOMOJI, pushRecentKaomoji, recentKaomoji } from "@/lib/kaomoji";

/** 카오모지 피커 — 카테고리 탭 + 최근 사용 (docs/specs/chat.md) */
export function KaomojiPicker({ onPick }: { onPick: (k: string) => void }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState(0);
  const [recent, setRecent] = useState<string[]>([]);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) setRecent(recentKaomoji());
  }, [open]);

  // 바깥 클릭으로 닫기
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  function pick(k: string) {
    pushRecentKaomoji(k);
    onPick(k);
    setOpen(false);
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="이모티콘 선택"
        aria-expanded={open}
        className="flex min-h-11 min-w-11 items-center justify-center rounded-md border-2 border-ink/20 bg-white text-lg transition hover:border-brick-yellow"
      >
        {"(^‿^)"}
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-30 mb-2 w-72 rounded-lg border-2 border-ink/15 bg-white p-2 shadow-xl">
          {recent.length > 0 && (
            <>
              <p className="px-1 text-[10px] font-bold opacity-40">최근 사용</p>
              <div className="mb-1 flex flex-wrap">
                {recent.map((k) => (
                  <KaomojiButton key={`r-${k}`} k={k} onPick={pick} />
                ))}
              </div>
            </>
          )}
          <div className="mb-1 flex gap-1">
            {KAOMOJI.map((c, i) => (
              <button
                key={c.label}
                type="button"
                onClick={() => setTab(i)}
                className={`rounded px-2 py-1 text-xs font-bold ${
                  tab === i ? "bg-ink text-white" : "bg-ink/5 hover:bg-ink/10"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
          <div className="flex max-h-40 flex-wrap overflow-y-auto">
            {KAOMOJI[tab].items.map((k) => (
              <KaomojiButton key={k} k={k} onPick={pick} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KaomojiButton({
  k,
  onPick,
}: {
  k: string;
  onPick: (k: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onPick(k)}
      className="rounded px-1.5 py-1 text-sm transition hover:bg-highlight/50"
    >
      {k}
    </button>
  );
}
