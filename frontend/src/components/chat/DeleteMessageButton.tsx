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
}: {
  label: string;
  confirmLabel: string;
  className: string;
  onDelete: () => void;
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
      onClick={() => {
        if (asking) {
          setAsking(false);
          onDelete();
        } else {
          setAsking(true);
        }
      }}
      aria-label="메시지 삭제"
      className={`${className} ${asking ? "font-bold text-brick-red opacity-100" : ""}`}
    >
      {asking ? confirmLabel : label}
    </button>
  );
}
