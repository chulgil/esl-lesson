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
  // 중복 전송 가드 — Safari 는 조합 확정 Enter 가 compositionend 후 keydown 으로
  // 한 번 더 오므로, 짧은 창 안의 연속 Enter 는 1회만 전송한다
  const lastSend = useRef(0);

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
        // Enter = 전송, Shift+Enter = 줄바꿈 — 전 기기·전 화면 공통 (2026-07-31 최종).
        // 한글 조합 중(isComposing) Enter 도 전송한다 — 조합 글자는 이미 value 에
        // 반영돼 있어 전체가 나간다 (카카오 PC 동작. isComposing 을 건너뛰면
        // "조합 확정용 Enter + 전송용 Enter" 두 번 눌러야 해 간헐 미전송으로 보고됨).
        // 중복 가드: Safari 가 같은 확정 Enter 를 keydown 으로 한 번 더 쏘는 케이스
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          const now = Date.now();
          if (now - lastSend.current < 150) return;
          lastSend.current = now;
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
