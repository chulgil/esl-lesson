"use client";

import { useEffect, useState } from "react";

/** 메시지 삭제 2탭 확인 버튼 — window.confirm 은 브라우저가 대화상자를
 *  차단하면 조용히 false 라 "버튼이 안 먹는" 것처럼 보인다 (2026-07-31).
 *  첫 탭 = "정말 지우기?" 로 전환, 3초 내 재탭 = 삭제, 지나면 원복. */
export function DeleteMessageButton({
  label,
  confirmLabel,
  className,
  onDelete,
  ariaLabel = "메시지 삭제",
  disabled = false,
}: {
  label: string;
  confirmLabel: string;
  className: string;
  onDelete: () => void;
  /** 메시지 외 다른 대상(목표 항목 등)에 재사용할 때의 접근성 라벨 */
  ariaLabel?: string;
  /** 요청 진행 중 등 — 중복 클릭 방지용 (기본 false) */
  disabled?: boolean;
}) {
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    if (!asking) return;
    const timer = setTimeout(() => setAsking(false), 3000);
    return () => clearTimeout(timer);
  }, [asking]);

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => {
        if (asking) {
          setAsking(false);
          onDelete();
        } else {
          setAsking(true);
        }
      }}
      aria-label={ariaLabel}
      className={`${className} ${asking ? "font-bold text-brick-red opacity-100" : ""} disabled:opacity-40`}
    >
      {asking ? confirmLabel : label}
    </button>
  );
}
