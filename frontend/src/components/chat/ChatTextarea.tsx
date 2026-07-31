"use client";

import { useEffect, useRef } from "react";

/** 자동 확장 채팅 입력 — Enter = 줄바꿈, 전송은 버튼으로만 (카카오톡 모바일 방식,
 *  2026-07-31 요청 — Enter 전송에서 변경). 최대 8줄, docs/specs/chat.md.
 *
 *  높이는 내용에 맞춰 자라고 8줄에서 멈춘 뒤 내부 스크롤. 전송으로 값이 비면
 *  1줄로 복귀. */

const MAX_LINES = 8;

export function ChatTextarea({
  value,
  onChange,
  onPasteImage,
  placeholder,
  className,
  ariaLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  onPasteImage: (file: File) => void;
  placeholder: string;
  className: string;
  ariaLabel?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  // 값이 바뀔 때마다 내용 높이에 맞춤 — 8줄 상한은 CSS max-height 가 담당
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  return (
    <textarea
      ref={ref}
      value={value}
      rows={1}
      onChange={(e) => onChange(e.target.value)}
      onPaste={(e) => {
        // 클립보드 이미지 붙여넣기 → 파일 첨부와 같은 업로드 파이프라인
        const file = Array.from(e.clipboardData.files).find((f) =>
          f.type.startsWith("image/"),
        );
        if (file) {
          e.preventDefault();
          onPasteImage(file);
        }
      }}
      data-chat-input="1"
      placeholder={placeholder}
      maxLength={2000}
      aria-label={ariaLabel}
      style={{ maxHeight: `${MAX_LINES * 1.5}em` }}
      className={`resize-none overflow-y-auto leading-normal ${className}`}
    />
  );
}
