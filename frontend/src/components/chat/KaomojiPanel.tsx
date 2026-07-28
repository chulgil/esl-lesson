"use client";

import { useEffect, useState } from "react";
import { KAOMOJI, pushRecentKaomoji, recentKaomoji } from "@/lib/kaomoji";

/** 카오모지 패널 — 카테고리 탭 + 최근 사용 (docs/specs/chat.md).
 *  위치·토글은 ChatToolsMenu 가 담당하고, 이 컴포넌트는 내용만 그린다. */
export function KaomojiPanel({ onPick }: { onPick: (k: string) => void }) {
  const [tab, setTab] = useState(0);
  const [recent, setRecent] = useState<string[]>([]);

  useEffect(() => {
    setRecent(recentKaomoji());
  }, []);

  function pick(k: string) {
    pushRecentKaomoji(k);
    onPick(k);
  }

  return (
    <>
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
    </>
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
