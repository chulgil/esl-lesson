"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { NotifyEnableButton } from "@/components/chat/NotifyEnableButton";
import {
  BlankSheet,
  ExcelChrome,
  fakeFilename,
} from "@/components/chat/skins/ExcelChrome";
import { BackLink } from "@/components/nav/BackLink";
import { chatApi, type ChatConversation } from "@/lib/chat-api";
import { onChatEvent } from "@/lib/chat-signals";
import { useAppTheme } from "@/lib/theme";
import { CHAT_LABEL_OF } from "@/lib/theme-surfaces";
import { timeAgo } from "@/lib/time";

/** 대화 목록 — 테마별 위장 (docs/specs/chat.md 위장 테마).
 *  오피스 테마 = 공유 문서 목록(시트), 그 외 = 교환 노트 목록. */
export default function ChatListPage() {
  const theme = useAppTheme();
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
    return onChatEvent((msg) => {
      // chat.deleted: 삭제된 마지막 메시지 미리보기("삭제되었습니다") 즉시 반영
      if (
        msg.t === "chat.message" ||
        msg.t === "presence" ||
        msg.t === "chat.deleted"
      )
        load();
    });
  }, [load]);

  // 위장 문서 제목 (브라우저 탭 목록 대비) — 테마 라벨은 CHAT_LABEL_OF 가
  // 정본 ("교환 노트" 하드코딩은 cat/school/ocean 라벨을 무시했다, 2026-08-05)
  useEffect(() => {
    const prev = document.title;
    document.title =
      theme === "excel" ? fakeFilename("공유문서함") : CHAT_LABEL_OF[theme];
    return () => {
      document.title = prev;
    };
  }, [theme]);

  if (theme === "excel") return <ExcelList items={items} error={error} />;
  return <NoteList items={items} error={error} />;
}

/* --- 교환 노트 목록 (종이 테마 공용) --------------------------------------- */

function NoteList({
  items,
  error,
}: {
  items: ChatConversation[] | null;
  error: string | null;
}) {
  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex items-center gap-4">
        <BackLink href="/" label="홈" />
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">교환 노트</span>
        </h1>
        <Link
          href="/friends"
          className="ml-auto text-sm font-bold text-brick-blue hover:underline"
        >
          친구 관리 →
        </Link>
      </header>

      {error && <p className="mb-4 text-sm text-brick-red">{error}</p>}

      <div className="mx-auto flex max-w-md flex-col gap-2">
        <NotifyEnableButton label="새 글 알림 켜기" />
        {items?.map((c) => (
          <Link
            key={c.conversation_id}
            href={`/chat/${c.user_id}`}
            className="flex items-center gap-3 rounded-lg border-2 border-ink/10 bg-white p-3 shadow-sm transition hover:-translate-y-0.5 hover:border-brick-blue/40"
          >
            <span className="relative">
              <Avatar name={c.name} />
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
                  {c.last_message ?? "첫 줄을 적어보세요"}
                </span>
                {c.unread > 0 && (
                  <span className="ml-auto shrink-0 rounded-full bg-brick-red px-2 py-0.5 text-xs font-bold text-brick-label">
                    {c.unread > 99 ? "99+" : c.unread}
                  </span>
                )}
              </span>
            </span>
          </Link>
        ))}

        {items && items.length === 0 && (
          <div className="rounded-lg border-2 border-ink/10 bg-white p-6 text-center text-sm opacity-60">
            아직 노트가 없어요.
            <br />
            <Link href="/friends" className="font-bold text-brick-blue">
              친구 목록
            </Link>
            에서 첫 줄을 적어보세요 (๑˃ᴗ˂)ﻭ
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

/* --- 공유 문서 목록 (오피스 테마 위장, ExcelChrome) ------------------------- */

function ExcelList({
  items,
  error,
}: {
  items: ChatConversation[] | null;
  error: string | null;
}) {
  return (
    <ExcelChrome
      filename={fakeFilename("공유문서함")}
      formula='=FILES("shared", SORT_BY_MODIFIED)'
      cellRef="A2"
      sheetTabs={["문서함", "보관"]}
      statusRight={<span>{items ? `${items.length}개 항목` : ""}</span>}
      blank={<BlankSheet cols={["A", "B", "C", "D"]} />}
    >
      {error && (
        <p className="border-b border-[#d8dde3] bg-[#fff4f4] px-3 py-1 text-xs text-[#c0504d]">
          {error}
        </p>
      )}
      <div className="flex items-center gap-2 border-b border-[#d8dde3] bg-white px-2 py-1">
        <NotifyEnableButton label="변경 알림 받기" variant="excel" />
        <Link
          href="/friends"
          className="ml-auto text-xs text-[#217346] hover:underline"
        >
          구성원 관리
        </Link>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-[#f6f8f9] text-left text-xs text-[#666]">
              <th className="w-9 border border-[#d8dde3] px-1.5 py-0.5 font-normal">
                {" "}
              </th>
              <th className="border border-[#d8dde3] px-2 py-0.5 font-normal">
                이름
              </th>
              <th className="w-28 border border-[#d8dde3] px-2 py-0.5 font-normal">
                수정한 날짜
              </th>
              <th className="w-24 border border-[#d8dde3] px-2 py-0.5 font-normal">
                변경
              </th>
              <th className="w-20 border border-[#d8dde3] px-2 py-0.5 font-normal">
                공동 작성
              </th>
            </tr>
          </thead>
          <tbody>
            {items?.map((c, i) => (
              <tr key={c.conversation_id} className="hover:bg-[#f6f8f9]">
                <td className="border border-[#e4e8ec] px-1.5 py-1.5 text-center text-xs text-[#888]">
                  {i + 1}
                </td>
                <td className="border border-[#e4e8ec] px-2 py-1.5">
                  <Link
                    href={`/chat/${c.user_id}`}
                    className="flex items-center gap-1.5 hover:underline"
                  >
                    <SheetIcon />
                    {c.name}_공유.xlsx
                  </Link>
                </td>
                <td className="border border-[#e4e8ec] px-2 py-1.5 text-xs text-[#666]">
                  {c.last_message_at ? timeAgo(c.last_message_at) : "-"}
                </td>
                <td className="border border-[#e4e8ec] px-2 py-1.5 text-xs">
                  {c.unread > 0 ? (
                    <b className="text-[#217346]">변경 {c.unread}건</b>
                  ) : (
                    <span className="text-[#999]">-</span>
                  )}
                </td>
                <td className="border border-[#e4e8ec] px-2 py-1.5 text-xs text-[#666]">
                  {c.online ? "1명" : "0명"}
                </td>
              </tr>
            ))}
            {items && items.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="border border-[#e4e8ec] px-2 py-6 text-center text-xs text-[#999]"
                >
                  공유된 문서가 없습니다.{" "}
                  <Link
                    href="/friends"
                    className="text-[#217346] hover:underline"
                  >
                    구성원 관리
                  </Link>
                </td>
              </tr>
            )}
            {/* 빈 행 채우기 */}
            {Array.from({ length: Math.max(0, 14 - (items?.length ?? 0)) }).map(
              (_, i) => (
                <tr key={`e-${i}`}>
                  <td className="border border-[#e4e8ec] px-1.5 py-1.5 text-center text-xs text-[#bbb]">
                    {(items?.length ?? 0) + i + 1}
                  </td>
                  <td className="border border-[#e4e8ec]"> </td>
                  <td className="border border-[#e4e8ec]"> </td>
                  <td className="border border-[#e4e8ec]"> </td>
                  <td className="border border-[#e4e8ec]"> </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
    </ExcelChrome>
  );
}

function SheetIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#217346"
      strokeWidth="2"
      aria-hidden
    >
      <rect x="3" y="3" width="18" height="18" rx="1" />
      <path d="M3 9h18M9 3v18" />
    </svg>
  );
}
