"use client";

import { useEffect, useState } from "react";
import {
  getPushState,
  type PushState,
  sendTestPush,
  subscribePush,
  unsubscribePush,
} from "@/lib/push";

/** 복습 리마인더 알림 토글 — 매일 저녁 8시, 밀린 복습이 있을 때만 (P3) */
export function PushReminderCard() {
  const [state, setState] = useState<PushState | "loading">("loading");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    getPushState()
      .then(setState)
      .catch(() => setState("unsupported"));
  }, []);

  async function toggle() {
    setBusy(true);
    setMessage(null);
    try {
      if (state === "subscribed") {
        await unsubscribePush();
        setState("idle");
      } else {
        setState(await subscribePush());
      }
    } catch {
      setMessage("설정에 실패했어요 — 잠시 후 다시 시도해주세요.");
    }
    setBusy(false);
  }

  async function handleTest() {
    setBusy(true);
    setMessage(null);
    try {
      const { sent, errors } = await sendTestPush();
      setMessage(
        sent > 0
          ? "테스트 알림을 보냈어요 — 잠시 후 도착해요."
          : errors > 0
            ? "서버에서 푸시 발송에 실패했어요 — 서버 알림 설정(VAPID) 점검이 필요해요."
            : "등록된 기기가 없어요 — 알림을 다시 켜주세요.",
      );
    } catch {
      setMessage("테스트 발송에 실패했어요.");
    }
    setBusy(false);
  }

  if (state === "loading" || state === "disabled") return null;

  return (
    <section className="mt-10 max-w-lg">
      <p className="mb-1 text-sm font-bold">알림</p>
      <p className="mb-3 text-xs opacity-60">
        매일 저녁 8시, 밀린 복습이 있을 때만 알려드려요. 브라우저를 닫아도
        도착해요.
      </p>

      {state === "unsupported" && (
        <p className="rounded-md border-2 border-ink/10 bg-white p-3 text-xs opacity-70">
          이 브라우저는 푸시 알림을 지원하지 않아요. iPhone은 사파리 공유 →
          &ldquo;홈 화면에 추가&rdquo; 후 앱에서 켤 수 있어요.
        </p>
      )}
      {state === "denied" && (
        <p className="rounded-md border-2 border-ink/10 bg-white p-3 text-xs opacity-70">
          알림이 차단되어 있어요 — 브라우저 주소창의 사이트 설정에서 알림을
          허용한 뒤 다시 시도해주세요.
        </p>
      )}

      {(state === "idle" || state === "subscribed") && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={busy}
            onClick={toggle}
            aria-pressed={state === "subscribed"}
            className={`min-h-11 rounded-md border-2 px-4 text-sm font-bold transition disabled:opacity-50 ${
              state === "subscribed"
                ? "border-brick-green bg-brick-green/10 text-brick-green"
                : "border-ink/20 bg-white hover:border-ink/50"
            }`}
          >
            {state === "subscribed"
              ? "복습 리마인더 켜짐"
              : "복습 리마인더 켜기"}
          </button>
          {state === "subscribed" && (
            <button
              type="button"
              disabled={busy}
              onClick={handleTest}
              className="min-h-11 rounded-md border-2 border-ink/20 bg-white px-4 text-sm font-bold transition hover:border-ink/50 disabled:opacity-50"
            >
              테스트 알림 보내기
            </button>
          )}
        </div>
      )}
      {message && <p className="mt-2 text-xs opacity-70">{message}</p>}
      <button
        type="button"
        onClick={() =>
          window.dispatchEvent(new Event("esl-open-notif-guide"))
        }
        className="mt-3 text-xs font-bold text-brick-blue hover:underline"
      >
        알림 설정 가이드 보기 (Mac/Windows/모바일)
      </button>
    </section>
  );
}
