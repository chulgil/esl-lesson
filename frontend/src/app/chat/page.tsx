"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { BackLink } from "@/components/nav/BackLink";
import { chatApi, type ChatConversation } from "@/lib/chat-api";
import { onChatEvent } from "@/lib/chat-signals";

/** 대화 목록 — 접속 점·마지막 메시지·안읽음 배지 (docs/specs/chat.md) */
export default function ChatListPage() {
  const [items, setItems] = useState<ChatConversation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    chatApi
      .conversations()
      .then((res) => setItems(res.items))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
    // 새 메시지·프레즌스 변화 → 목록 갱신 (WS 이벤트 버스 구독)
    return onChatEvent((msg) => {
      if (msg.t === "chat.message" || msg.t === "presence") load();
    });
  }, [load]);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex items-center gap-4">
        <BackLink href="/" label="홈" />
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">채팅</span>
        </h1>
        <Link
          href="/friends"
          className="ml-auto text-sm font-bold text-brick-blue hover:underline"
        >
          친구 관리 →
        </Link>
      </header>

      {error && <p className="mb-4 text-sm text-brick-red">{error}</p>}

      <div className="mx-auto flex max-w-lg flex-col gap-2">
        {items?.map((c) => (
          <Link
            key={c.conversation_id}
            href={`/chat/${c.user_id}`}
            className="flex items-center gap-3 rounded-lg border-2 border-ink/10 bg-white p-3 shadow-sm transition hover:-translate-y-0.5 hover:border-brick-blue/40"
          >
            <span className="relative">
              <Avatar name={c.name} />
              {/* 접속 점 — invite_hub 프레즌스 (스펙 5) */}
              <span
                aria-label={c.online ? "접속 중" : "미접속"}
                className={`absolute -right-0.5 -bottom-0.5 h-3 w-3 rounded-full border-2 border-white ${
                  c.online ? "bg-brick-green" : "bg-ink/20"
                }`}
              />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-baseline gap-2">
                <b className="truncate">{c.name}</b>
                {c.last_message_at && (
                  <span className="ml-auto shrink-0 text-xs opacity-40">
                    {timeAgo(c.last_message_at)}
                  </span>
                )}
              </span>
              <span className="mt-0.5 flex items-center gap-2">
                <span className="truncate text-sm opacity-60">
                  {c.last_message ?? "대화를 시작해보세요"}
                </span>
                {c.unread > 0 && (
                  <span className="ml-auto shrink-0 rounded-full bg-brick-red px-2 py-0.5 text-xs font-bold text-white">
                    {c.unread > 99 ? "99+" : c.unread}
                  </span>
                )}
              </span>
            </span>
          </Link>
        ))}

        {items && items.length === 0 && (
          <div className="rounded-lg border-2 border-ink/10 bg-white p-6 text-center text-sm opacity-60">
            아직 대화가 없어요.
            <br />
            <Link href="/friends" className="font-bold text-brick-blue">
              친구 목록
            </Link>
            에서 메시지를 보내보세요 (๑˃ᴗ˂)ﻭ
          </div>
        )}
        {items === null && !error && (
          <p className="py-8 text-center text-sm opacity-40">불러오는 중...</p>
        )}
      </div>
    </main>
  );
}

/** 닉네임 이니셜 아바타 — 구글 프로필 사진은 실명 이니셜·사진이 포함되므로
 *  채팅에서는 절대 사용하지 않는다 (2026-07-27 결정). 색상은 닉네임 해시로 고정. */
const AVATAR_COLORS = [
  "bg-brick-red/15 text-brick-red",
  "bg-brick-blue/15 text-brick-blue",
  "bg-brick-green/15 text-brick-green",
  "bg-brick-yellow/30 text-ink",
  "bg-highlight/50 text-ink",
];

function Avatar({ name }: { name: string }) {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) % 997;
  const color = AVATAR_COLORS[hash % AVATAR_COLORS.length];
  return (
    <span
      className={`flex h-11 w-11 items-center justify-center rounded-full border-2 border-ink/10 font-bold ${color}`}
    >
      {name.slice(0, 1) || "?"}
    </span>
  );
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "방금";
  if (min < 60) return `${min}분 전`;
  const hours = Math.floor(min / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}
