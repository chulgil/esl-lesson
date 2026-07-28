"use client";

import { useEffect, useRef, useState } from "react";
import { KaomojiPanel } from "@/components/chat/KaomojiPanel";
import { WordSharePanel } from "@/components/chat/WordSharePanel";
import type { ShareableItem } from "@/lib/chat-api";

type View = "menu" | "word" | "kaomoji";

/** 채팅 도구 통합 메뉴 — 입력창 폭 확보를 위해 단어카드·사진·이모티콘 3버튼을
 *  "+" 아이콘 1개로 묶고, 누르면 입력줄 위로 플로팅 메뉴가 뜬다 (2026-07-28 요청).
 *  사진은 즉시 파일창, 단어·이모티콘은 메뉴 안에서 패널로 전환된다. */
export function ChatToolsMenu({
  onPickItem,
  onPickImage,
  onPickKaomoji,
  variant = "note",
}: {
  onPickItem: (item: ShareableItem) => void;
  onPickImage: (file: File) => void;
  onPickKaomoji: (k: string) => void;
  variant?: "note" | "excel";
}) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<View>("menu");
  const rootRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const excel = variant === "excel";

  // 바깥 클릭으로 닫기
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
      <input
        ref={fileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onPickImage(file);
          e.target.value = ""; // 같은 파일 재선택 허용
          setOpen(false);
        }}
      />
      <button
        type="button"
        onClick={() => {
          setOpen((v) => !v);
          setView("menu");
        }}
        aria-label="첨부·이모티콘 메뉴"
        aria-expanded={open}
        className={
          excel
            ? "flex min-h-9 min-w-9 items-center justify-center rounded-sm border border-[#c9cfd6] bg-[#f6f8f9] text-base font-bold hover:bg-[#e2efda]"
            : "flex min-h-11 min-w-11 items-center justify-center rounded-md border-2 border-ink/20 bg-white text-xl font-bold transition hover:border-brick-green"
        }
      >
        +
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-30 mb-2 w-72 max-w-[calc(100vw-2.5rem)] rounded-lg border-2 border-ink/15 bg-white p-2 shadow-xl">
          {view === "menu" && (
            <div className="flex flex-col">
              <MenuItem onClick={() => setView("word")} icon="+">
                단어 카드 공유
              </MenuItem>
              <MenuItem
                onClick={() => fileRef.current?.click()}
                icon={<ClipIcon />}
              >
                사진 첨부
              </MenuItem>
              <MenuItem onClick={() => setView("kaomoji")} icon="(^‿^)">
                이모티콘
              </MenuItem>
            </div>
          )}
          {view === "word" && (
            <WordSharePanel
              onPick={(item) => {
                onPickItem(item);
                setOpen(false);
              }}
            />
          )}
          {view === "kaomoji" && (
            <KaomojiPanel
              onPick={(k) => {
                onPickKaomoji(k);
                setOpen(false);
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}

function MenuItem({
  onClick,
  icon,
  children,
}: {
  onClick: () => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-11 items-center gap-3 rounded px-2 text-left text-sm font-bold transition hover:bg-highlight/40"
    >
      <span className="flex w-10 shrink-0 items-center justify-center text-base">
        {icon}
      </span>
      {children}
    </button>
  );
}

function ClipIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  );
}
