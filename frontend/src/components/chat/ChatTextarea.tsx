"use client";

import { useEffect, useRef } from "react";

/** 자동 확장 채팅 입력 — Enter = 전송, Shift+Enter = 줄바꿈.
 *  전 기기·전 화면(대화방/플로팅 위젯) 공통 (2026-07-31 최종 확정 — 기기별
 *  분기는 혼선만 낳아 폐기). 최대 8줄 자동 확장 후 내부 스크롤, 전송 시
 *  1줄 복귀. IME 조합 중/직후 Enter 가드 (한글 오전송 방지). docs/specs/chat.md */

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
  // Safari(WebKit)는 조합 확정 Enter 를 compositionend 이후 keydown
  // (isComposing=false)으로 발화 — 확정 직후 Enter 를 전송으로 오인해
  // 한글 마지막 글자 확정이 곧장 전송되는 버그 방지 (2026-07-31 심층 리뷰)
  const lastCompositionEnd = useRef(0);

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
      onCompositionEnd={() => {
        lastCompositionEnd.current = Date.now();
      }}
      onKeyDown={(e) => {
        // Enter = 전송, Shift+Enter = 줄바꿈 — 전 기기·전 화면 공통 (2026-07-31 최종 확정).
        // isComposing + compositionend 직후 가드 — WebKit IME 오전송 방지
        if (
          e.key === "Enter" &&
          !e.shiftKey &&
          !e.nativeEvent.isComposing &&
          // 30ms: Safari 의 조합확정 후행 keydown(<5ms)만 거르고 사람 Enter(>50ms)는 통과
          Date.now() - lastCompositionEnd.current > 30
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
