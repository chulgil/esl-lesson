"use client";

import { useRef } from "react";

/** 이미지 첨부 버튼 — 클립 아이콘, 파일 선택 즉시 업로드 (docs/specs/chat.md) */
export function ImageAttachButton({
  onPick,
  variant = "note",
}: {
  onPick: (file: File) => void;
  variant?: "note" | "excel";
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onPick(file);
          e.target.value = ""; // 같은 파일 재선택 허용
        }}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        aria-label="이미지 첨부"
        className={
          variant === "excel"
            ? "flex min-h-9 min-w-9 items-center justify-center rounded-sm border border-[#c9cfd6] bg-[#f6f8f9] hover:bg-[#e2efda]"
            : "flex min-h-11 min-w-11 items-center justify-center rounded-md border-2 border-ink/20 bg-white transition hover:border-brick-green"
        }
      >
        <ClipIcon />
      </button>
    </>
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
