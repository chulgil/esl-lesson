"use client";

import { useEffect, useState } from "react";
import { setChatFloating, useChatFloating } from "@/lib/chat-mode";
import {
  getPushState,
  type PushState,
  sendTestPush,
  showLocalTestNotification,
  subscribePush,
  unsubscribePush,
} from "@/lib/push";

/** 채팅창 설정 — 표시 방식(플로팅/도킹) + 새 글 브라우저 알림.
 *  알림 구독은 복습 리마인더와 같은 VAPID 구독을 공유한다 (docs/specs/chat.md). */
export function ChatModeCard() {
  const floating = useChatFloating();
  const [push, setPush] = useState<PushState | "loading">("loading");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    getPushState()
      .then(setPush)
      .catch(() => setPush("unsupported"));
  }, []);

  async function toggleNotify() {
    setBusy(true);
    setMessage(null);
    try {
      if (push === "subscribed") {
        await unsubscribePush();
        setPush("idle");
      } else {
        setPush(await subscribePush());
      }
    } catch {
      setMessage("알림 설정에 실패했어요 — 잠시 후 다시 시도해주세요.");
    }
    setBusy(false);
  }

  async function handleTest() {
    setBusy(true);
    setMessage(null);
    // 로컬(서버 무관) + 서버 푸시를 함께 쏴서 어느 구간이 막혔는지 분리 진단
    const localShown = await showLocalTestNotification();
    try {
      const { sent, errors } = await sendTestPush();
      if (sent > 0) {
        setMessage(
          localShown
            ? "테스트 알림 2개(로컬·서버)를 보냈어요 — 하나도 안 보이면 OS 알림 설정(macOS: 시스템 설정 > 알림, Windows: 설정 > 알림)에서 이 브라우저를 허용하고 방해금지 모드를 꺼주세요."
            : "서버 발송은 됐지만 로컬 표시가 실패했어요 — 브라우저 알림 권한을 확인해주세요.",
        );
      } else if (errors > 0) {
        setMessage(
          "서버에서 푸시 발송에 실패했어요 — 서버 알림 설정(VAPID) 점검이 필요해요. 로컬 알림이 보였다면 브라우저 쪽은 정상이에요.",
        );
      } else {
        setMessage("등록된 기기가 없어요 — 알림을 다시 켜주세요.");
      }
    } catch {
      setMessage("테스트 발송에 실패했어요.");
    }
    setBusy(false);
  }

  return (
    <section className="mt-10 max-w-lg">
      <p className="mb-1 text-sm font-bold">채팅창</p>
      <p className="mb-3 text-xs opacity-60">
        체크 해제하면 팝업 대신 화면 우측에 항상 붙어있는 패널로 바뀌어요.
      </p>
      <label className="flex min-h-11 max-w-fit cursor-pointer items-center gap-2 rounded-md border-2 border-ink/20 bg-white px-4 text-sm font-bold transition hover:border-ink/50">
        <input
          type="checkbox"
          checked={floating}
          onChange={(e) => setChatFloating(e.target.checked)}
          className="h-4 w-4"
        />
        플로팅 (우하단 팝업)
      </label>

      <p className="mt-5 mb-1 text-sm font-bold">새 글 알림</p>
      <p className="mb-3 text-xs opacity-60">
        켜두면 탭이 백그라운드이거나 브라우저를 닫아도 새 메시지를 브라우저
        알림으로 받아요. (복습 리마인더와 같은 알림 설정을 사용해요)
      </p>
      {push === "unsupported" && (
        <p className="rounded-md border-2 border-ink/10 bg-white p-3 text-xs opacity-70">
          이 브라우저는 푸시 알림을 지원하지 않아요. iPhone은 사파리 공유 →
          &ldquo;홈 화면에 추가&rdquo; 후 앱에서 켤 수 있어요.
        </p>
      )}
      {push === "denied" && (
        <p className="rounded-md border-2 border-ink/10 bg-white p-3 text-xs opacity-70">
          알림이 차단되어 있어요 — 브라우저 주소창의 사이트 설정에서 알림을
          허용한 뒤 다시 시도해주세요.
        </p>
      )}
      {(push === "idle" || push === "subscribed") && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={busy}
            onClick={toggleNotify}
            aria-pressed={push === "subscribed"}
            className={`min-h-11 rounded-md border-2 px-4 text-sm font-bold transition disabled:opacity-50 ${
              push === "subscribed"
                ? "border-brick-green bg-brick-green/10 text-brick-green"
                : "border-ink/20 bg-white hover:border-ink/50"
            }`}
          >
            {push === "subscribed" ? "새 글 알림 켜짐" : "새 글 알림 켜기"}
          </button>
          {push === "subscribed" && (
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
    </section>
  );
}
