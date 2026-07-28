"use client";

import { useEffect, useState } from "react";
import { chatApi, type ShareableItem } from "@/lib/chat-api";

/** 학습 단어 공유 패널 — 내 학습 항목 검색 → 카드 첨부 (docs/specs/chat.md).
 *  위치·토글은 ChatToolsMenu 가 담당하고, 이 컴포넌트는 내용만 그린다. */
export function WordSharePanel({
  onPick,
}: {
  onPick: (item: ShareableItem) => void;
}) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<ShareableItem[]>([]);

  // 첫 표시 + 검색어 변경 시 조회 (300ms 디바운스)
  useEffect(() => {
    const timer = setTimeout(() => {
      chatApi
        .shareableItems(q)
        .then((res) => setItems(res.items))
        .catch(() => setItems([]));
    }, 300);
    return () => clearTimeout(timer);
  }, [q]);

  return (
    <>
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
            onClick={() => onPick(item)}
            className="flex items-baseline gap-2 rounded px-2 py-1.5 text-left text-sm transition hover:bg-highlight/40"
          >
            <b>{item.en_text}</b>
            <span className="truncate text-xs opacity-60">{item.ko_text}</span>
          </button>
        ))}
        {items.length === 0 && (
          <p className="py-4 text-center text-xs opacity-40">
            공유할 단어가 없어요
          </p>
        )}
      </div>
    </>
  );
}
