"use client";

import { useEffect, useState } from "react";
import { getPushState, subscribePush, type PushState } from "@/lib/push";

/** 브라우저 알림 켜기 — 기존 VAPID 푸시 구독 재사용 (docs/specs/chat.md 알림).
 *  구독되면 오프라인·백그라운드에서도 새 메시지 알림을 받는다. */
export function NotifyEnableButton({
  label,
  variant = "note",
}: {
  label: string;
  variant?: "note" | "excel";
}) {
  const [state, setState] = useState<PushState | "loading" | "error">(
    "loading",
  );

  useEffect(() => {
    getPushState()
      .then(setState)
      .catch(() => setState("error"));
  }, []);

  async function enable() {
    setState("loading");
    try {
      setState(await subscribePush());
    } catch {
      setState("error");
    }
  }

  // 이미 구독됨·미지원·서버 미설정이면 조용히 숨김 (설정 화면에서 관리)
  if (
    state === "subscribed" ||
    state === "unsupported" ||
    state === "disabled"
  ) {
    return null;
  }

  if (state === "denied") {
    return (
      <p
        className={
          variant === "excel"
            ? "text-xs text-[#999]"
            : "text-center text-xs opacity-40"
        }
      >
        브라우저 설정에서 알림 차단을 해제하면 새 소식을 받을 수 있어요
      </p>
    );
  }

  return (
    <span className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        disabled={state === "loading"}
        onClick={enable}
        className={
          variant === "excel"
            ? "min-h-7 rounded-sm border border-[#c9cfd6] bg-[#f6f8f9] px-2.5 text-xs hover:bg-[#e2efda] disabled:opacity-40"
            : "min-h-10 rounded-md border-2 border-brick-blue/40 bg-white px-3 text-sm font-bold text-brick-blue transition hover:border-brick-blue disabled:opacity-40"
        }
      >
        {state === "loading" ? "..." : label}
      </button>
      {/* 실패를 조용히 삼키면 켜진 줄 착각한다 — 재시도 유도 문구 필수 (2026-07-28 보고) */}
      {state === "error" && (
        <span
          className={
            variant === "excel"
              ? "text-xs text-[#c0504d]"
              : "text-xs text-brick-red"
          }
        >
          알림 설정에 실패했어요 — 다시 눌러주세요
        </span>
      )}
    </span>
  );
}
