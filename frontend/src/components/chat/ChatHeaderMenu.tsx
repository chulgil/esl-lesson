"use client";

import { useEffect, useRef, useState } from "react";

/** 대화방 헤더 케밥 메뉴 — "..." 버튼 → 드롭다운 (docs/specs/chat-notice.md).
 *  지금은 공지 항목 1개뿐이지만, 향후 대화방 설정 항목의 진입점으로 확장된다.
 *  ChatToolsMenu 와 동일한 바깥 클릭 닫힘 패턴을 재사용한다. */
export function ChatHeaderMenu({
  excel,
  items,
  className = "",
}: {
  excel: boolean;
  items: { label: string; onClick: () => void }[];
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div ref={rootRef} className={`relative shrink-0 ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="대화방 메뉴"
        aria-expanded={open}
        className={
          excel
            ? "flex min-h-8 min-w-8 items-center justify-center rounded-sm text-sm font-bold text-white/80 hover:bg-white/10 hover:text-white"
            : "flex min-h-11 min-w-11 items-center justify-center text-lg font-bold opacity-60 hover:opacity-100"
        }
      >
        ...
      </button>

      {open && (
        <div
          className={
            excel
              ? "absolute top-full right-0 z-30 mt-1 min-w-32 border border-[#c9cfd6] bg-white py-1 text-xs whitespace-nowrap text-[#24292f] shadow-lg"
              : "absolute top-full right-0 z-30 mt-1 min-w-32 rounded-md border-2 border-ink/15 bg-white py-1 text-sm whitespace-nowrap shadow-xl"
          }
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => {
                setOpen(false);
                item.onClick();
              }}
              className={
                excel
                  ? "block min-h-8 w-full px-3 py-1.5 text-left hover:bg-[#f6f8f9]"
                  : "block min-h-11 w-full px-3 py-2 text-left font-bold hover:bg-highlight/40"
              }
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
