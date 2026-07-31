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
  // Safari(WebKit)는 조합 확정 Enter 를 compositionend 이후 keydown
  // (isComposing=false)으로 발화 — 확정 직후 Enter 를 전송으로 오인해
  // 한글 마지막 글자 확정이 곧장 전송되는 버그 방지 (2026-07-31 심층 리뷰)
  const lastCompositionEnd = useRef(0);

  // PC 판별 — 화면 폭 단독(sm 640px, ChatWidget isDesktop 동일 기준).
  // pointer:fine 병행 판별은 터치스크린 노트북에서 primary=coarse 로 오판해
  // PC 인데 Enter 전송이 죽는다 (2026-07-31 보고 — 태블릿 가로모드 오적용보다
  // PC 오동작이 치명적이라 폭 단독으로 회귀)
  const [enterSends, setEnterSends] = useState(false);
  useEffect(() => {
    const wide = window.matchMedia("(min-width: 640px)");
    const apply = () => setEnterSends(wide.matches);
    apply();
    wide.addEventListener("change", apply);
    return () => wide.removeEventListener("change", apply);
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
      onCompositionEnd={() => {
        lastCompositionEnd.current = Date.now();
      }}
      onKeyDown={(e) => {
        // PC: Enter 전송 (Shift+Enter 줄바꿈) / 모바일: Enter 는 그대로 줄바꿈.
        // isComposing + compositionend 직후 100ms 이중 가드 — WebKit IME 오전송 방지
        if (
          enterSends &&
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
