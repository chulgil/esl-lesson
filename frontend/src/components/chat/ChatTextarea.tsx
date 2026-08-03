"use client";

import { useEffect, useRef } from "react";

/** 자동 확장 채팅 입력 — Enter = 전송, Shift+Enter = 줄바꿈.
 *  전 기기·전 화면(대화방/플로팅 위젯) 공통 (2026-07-31 최종 확정 — 기기별
 *  분기는 혼선만 낳아 폐기). 최대 8줄 자동 확장 후 내부 스크롤, 전송 시
 *  1줄 복귀. 한글 조합 중 Enter 는 조합 확정 후 전송(예약). docs/specs/chat.md */

const MAX_LINES = 8;
// 조합 확정(compositionend)이 오지 않는 IME 대비 — 예약 전송을 놓치지 않는 최후 방어
const PENDING_SEND_FALLBACK_MS = 150;

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

  // 한글 잔여 글자("안녕하세요" → "요") 근본 대책 (2026-08-03 3차).
  // 조합 중에 전송하면 입력창이 비워지는데, 그 뒤 IME 가 확정 글자를 되돌려 넣어
  // 잔여가 남는다. 커밋을 사후에 지우는 방식은 브라우저·IME 마다 이벤트 순서가
  // 달라 실패했다(1·2차). 그래서 조합 중 Enter 는 **전송을 예약만** 하고,
  // 조합이 끝난 뒤(= 되돌려 넣을 글자가 더 없는 시점) 최신 값으로 보낸다.
  const pendingSend = useRef(false);
  const fallbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 조합 여부는 composition 이벤트로 직접 추적 — 일부 브라우저는 확정 Enter 의
  // keydown 에 isComposing=false 를 실어 보내면서 실제 커밋은 그 뒤에 한다
  const composing = useRef(false);
  // 예약 전송은 '조합 확정이 반영된 다음 렌더'의 onSend 로 보내야 마지막 글자가 실린다
  const sendRef = useRef(onSend);
  sendRef.current = onSend;

  const cancelFallback = () => {
    if (fallbackTimer.current) clearTimeout(fallbackTimer.current);
    fallbackTimer.current = null;
  };

  const flushPendingSend = () => {
    if (!pendingSend.current) return;
    pendingSend.current = false;
    cancelFallback();
    lastSend.current = Date.now();
    sendRef.current();
  };

  // 조합 종료 시점엔 확정 input 이 아직 state 에 반영되기 전일 수 있다 —
  // 한 틱 뒤로 미뤄 최신 값으로 전송
  const schedulePendingSend = () => {
    if (pendingSend.current) setTimeout(flushPendingSend, 0);
  };

  useEffect(() => cancelFallback, []);

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
      onChange={(e) => {
        onChange(e.target.value);
        // 조합이 끝난 뒤의 입력(확정 커밋)이면 예약 전송을 태운다 —
        // compositionend 를 놓치는 IME 대비 두 번째 경로
        if (!(e.nativeEvent as InputEvent).isComposing) schedulePendingSend();
      }}
      onKeyDown={(e) => {
        // Enter = 전송, Shift+Enter = 줄바꿈 — 전 기기·전 화면 공통 (2026-07-31 최종).
        // 조합 중 Enter 도 "한 번만" 눌러 보낸다 (카카오 PC 동작) — 다만 즉시
        // 보내는 대신 조합 확정 뒤로 예약해 IME 잔여 글자를 원천 차단한다.
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          const now = Date.now();
          if (now - lastSend.current < 150) return;
          if (e.nativeEvent.isComposing || composing.current) {
            pendingSend.current = true;
            cancelFallback();
            fallbackTimer.current = setTimeout(
              flushPendingSend,
              PENDING_SEND_FALLBACK_MS,
            );
            return;
          }
          // 조합이 이미 끝난 Enter (Safari 의 재발화 포함) — 예약분을 흡수하고 지금 전송
          pendingSend.current = false;
          cancelFallback();
          lastSend.current = now;
          onSend();
        }
      }}
      onCompositionStart={() => {
        composing.current = true;
      }}
      onCompositionEnd={() => {
        composing.current = false;
        schedulePendingSend();
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
