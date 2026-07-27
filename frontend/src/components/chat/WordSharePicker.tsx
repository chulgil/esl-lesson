"use client";

import { useEffect, useRef, useState } from "react";
import { chatApi, type ShareableItem } from "@/lib/chat-api";

/** 학습 단어 공유 — 내 학습 항목 검색 → 카드 첨부 (docs/specs/chat.md) */
export function WordSharePicker({
  onPick,
}: {
  onPick: (item: ShareableItem) => void;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [items, setItems] = useState<ShareableItem[]>([]);
  const rootRef = useRef<HTMLDivElement>(null);

  // 열릴 때 + 검색어 변경 시 조회 (300ms 디바운스)
  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(() => {
      chatApi
        .shareableItems(q)
        .then((res) => setItems(res.items))
        .catch(() => setItems([]));
    }, 300);
    return () => clearTimeout(timer);
  }, [open, q]);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="학습 단어 공유"
        aria-expanded={open}
        className="flex min-h-11 min-w-11 items-center justify-center rounded-md border-2 border-ink/20 bg-white text-xl font-bold transition hover:border-brick-green"
      >
        +
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-30 mb-2 w-72 rounded-lg border-2 border-ink/15 bg-white p-2 shadow-xl">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="내 단어 검색..."
            className="mb-1.5 w-full rounded-md border-2 border-ink/15 px-2 py-1.5 text-sm focus:border-brick-blue focus:outline-none"
          />
          <div className="flex max-h-44 flex-col overflow-y-auto">
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  onPick(item);
                  setOpen(false);
                }}
                className="flex items-baseline gap-2 rounded px-2 py-1.5 text-left text-sm transition hover:bg-highlight/40"
              >
                <b>{item.en_text}</b>
                <span className="truncate text-xs opacity-60">
                  {item.ko_text}
                </span>
              </button>
            ))}
            {items.length === 0 && (
              <p className="py-4 text-center text-xs opacity-40">
                공유할 단어가 없어요
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
