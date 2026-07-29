"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { chatApi } from "@/lib/chat-api";
import { onChatEvent } from "@/lib/chat-signals";
import {
  notificationsApi,
  type NotificationItem,
} from "@/lib/notifications-api";
import { timeAgo } from "@/lib/time";

/** 네비 알림 벨 — 친구 요청·수락·게임 초대 알림 센터 (docs/specs/notifications.md).
 *  배지 = 알림 unread + 채팅 unread 합산 (2026-07-28 배지 일원화 —
 *  채팅 탭에는 배지가 없어 이중 계산 없음). 채팅 상세는 드롭다운
 *  첫 행 "새 메시지 N개" 요약으로 안내. */
export function NotificationBell() {
  const router = useRouter();
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [chatUnread, setChatUnread] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    notificationsApi
      .list()
      .then((res) => {
        setItems(res.items);
        setUnread(res.unread);
      })
      .catch(() => {});
    chatApi
      .unreadTotal()
      .then((res) => setChatUnread(res.total))
      .catch(() => {});
  }, []);

  useEffect(() => {
    load();
    // WS notif.new 가 주 갱신 경로 — 폴링은 이벤트 유실 대비 보조
    const timer = setInterval(load, 60000);
    const off = onChatEvent((msg) => {
      if (
        msg.t === "notif.new" ||
        msg.t === "chat.message" ||
        msg.t === "chat.read"
      )
        load();
    });
    return () => {
      clearInterval(timer);
      off();
    };
  }, [load]);

  // 라우트가 바뀌면 닫기 — 레이아웃에 상주해 이동 후에도 열린 채 남으면
  // 다음 클릭이 드롭다운 닫기에 소모돼 "메뉴가 안 눌린다"로 체감 (2026-07-29)
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // 바깥 클릭으로 닫기
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  function openItem(n: NotificationItem) {
    setOpen(false);
    // 이동을 막지 않도록 읽음 처리는 비동기 — await 하면 느린 네트워크에서
    // 클릭이 죽은 것처럼 보인다 (2026-07-29 메뉴 이동 불편 보고)
    notificationsApi
      .markRead({ ids: [n.id] })
      .then(load)
      .catch(() => {});
    const target = notifTarget(n);
    // 이미 대상 페이지면 push 가 무변화라 "이동 안 됨"으로 보인다 — 새로고침으로 반응
    if (window.location.pathname + window.location.search === target) {
      router.refresh();
    } else {
      router.push(target);
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={`알림${unread + chatUnread > 0 ? ` — ${unread + chatUnread}건` : ""}`}
        aria-expanded={open}
        className="relative flex min-h-11 min-w-11 items-center justify-center rounded-md transition hover:bg-ink/10"
      >
        <BellIcon />
        {unread + chatUnread > 0 && (
          <span className="absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-brick-red px-1 text-[10px] font-bold text-white">
            {unread + chatUnread > 99 ? "99+" : unread + chatUnread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute top-full right-0 z-50 mt-2 max-h-96 w-80 max-w-[calc(100vw-1rem)] overflow-y-auto rounded-lg border-2 border-ink/15 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-ink/10 px-3 py-2">
            <span className="text-sm font-bold">알림</span>
            <button
              type="button"
              onClick={() =>
                notificationsApi
                  .markRead({ all: true })
                  .then(load)
                  .catch(() => {})
              }
              className="text-xs font-bold text-brick-blue hover:underline"
            >
              모두 읽음
            </button>
          </div>

          {chatUnread > 0 && (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                router.push("/chat");
              }}
              className="flex w-full items-center gap-2 border-b border-ink/10 px-3 py-2 text-left text-sm font-bold transition hover:bg-highlight/40"
            >
              <span
                className="h-2 w-2 shrink-0 rounded-full bg-brick-blue"
                aria-hidden
              />
              새 메시지 {chatUnread}개
            </button>
          )}

          {items.map((n) => (
            <button
              key={n.id}
              type="button"
              onClick={() => openItem(n)}
              className="flex w-full items-start gap-2 px-3 py-2 text-left text-sm transition hover:bg-highlight/40"
            >
              <span
                className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                  n.read_at === null ? "bg-brick-blue" : "bg-transparent"
                }`}
                aria-hidden
              />
              <span className="flex-1">
                {notifText(n)}
                <span className="mt-0.5 block text-xs opacity-50">
                  {timeAgo(n.created_at)}
                </span>
              </span>
            </button>
          ))}

          {items.length === 0 && chatUnread === 0 && (
            <p className="px-3 py-8 text-center text-sm opacity-40">
              새 알림이 없어요
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function notifText(n: NotificationItem): string {
  const from = String(n.payload.from_name ?? "친구");
  if (n.type === "friend_request") return `${from} 님이 친구 요청을 보냈어요`;
  if (n.type === "friend_accepted")
    return `${from} 님이 친구 요청을 수락했어요`;
  if (n.type === "game_invite") return `${from} 님이 게임에 초대했어요`;
  // 알 수 없는 타입 (구버전 클라 대비) — 이름만 노출
  return `${from} 님의 새 알림`;
}

function notifTarget(n: NotificationItem): string {
  if (n.type === "game_invite")
    return `/game/${String(n.payload.game ?? "")}?join=${String(n.payload.code ?? "")}`;
  return "/friends";
}

function BellIcon() {
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
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  );
}
