"use client";

import { useEffect, useRef, useState } from "react";

/** 자동 확장 채팅 입력 — 기기별 Enter 동작 (2026-07-31 확정):
 *  - PC(sm 이상): Enter = 전송, Shift+Enter = 줄바꿈 (데스크톱 메신저 방식)
 *  - 모바일: Enter = 줄바꿈, 전송은 버튼만 (카카오톡 모바일 방식)
 *  최대 8줄 자동 확장 후 내부 스크롤, 전송으로 값이 비면 1줄 복귀.
 *  IME 조합 중 Enter 는 무시 (한글 오전송 방지). docs/specs/chat.md */

const MAX_LINES = 8;

export function ChatTextarea({
  value,
  onChange,
  onSend,
  onPasteImage,
  placeholder,
  className,
  ariaLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onPasteImage: (file: File) => void;
  placeholder: string;
  className: string;
  ariaLabel?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  // PC 판별 — ChatWidget 의 isDesktop 과 동일 기준(sm 640px)
  const [enterSends, setEnterSends] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 640px)");
    const apply = () => setEnterSends(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

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
      onKeyDown={(e) => {
        // PC: Enter 전송 (Shift+Enter 줄바꿈) / 모바일: Enter 는 그대로 줄바꿈
        if (
          enterSends &&
          e.key === "Enter" &&
          !e.shiftKey &&
          !e.nativeEvent.isComposing
        ) {
          e.preventDefault();
          onSend();
        }
      }}
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
