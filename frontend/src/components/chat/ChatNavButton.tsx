"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { chatApi } from "@/lib/chat-api";
import { onChatEvent } from "@/lib/chat-signals";

/** 네비 채팅 진입점 + 안읽음 배지 — WS 이벤트로 즉시 갱신 (docs/specs/chat.md 알림) */
export function ChatNavButton({ floating = false }: { floating?: boolean }) {
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    const load = () =>
      chatApi
        .unreadTotal()
        .then((res) => setUnread(res.total))
        .catch(() => {});
    load();
    // 서버 캐시(TTL 30초)가 있어 폴링 부담 없음 — WS 이벤트가 주 갱신 경로
    const timer = setInterval(load, 60000);
    const off = onChatEvent((msg) => {
      if (msg.t === "chat.message" || msg.t === "chat.read") load();
    });
    return () => {
      clearInterval(timer);
      off();
    };
  }, []);

  return (
    <Link
      href="/chat"
      aria-label={`채팅${unread > 0 ? ` — 안읽음 ${unread}개` : ""}`}
      className={
        floating
          ? "fixed top-3 right-3 z-40 flex h-11 w-11 items-center justify-center rounded-full border-2 border-ink/15 bg-white shadow-md sm:hidden"
          : "relative flex min-h-11 items-center gap-2 rounded-md px-3 font-bold transition hover:bg-ink/10"
      }
    >
      <ChatIcon />
      {!floating && <span className="hidden lg:inline">채팅</span>}
      {unread > 0 && (
        <span className="absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-brick-red px-1 text-[10px] font-bold text-white">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}

function ChatIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8Z" />
    </svg>
  );
}
