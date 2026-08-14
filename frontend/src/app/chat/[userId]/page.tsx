"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LangPairBadge } from "@/components/chat/LangPairBadge";
import { BackLink } from "@/components/nav/BackLink";
import { roomsApi, type ChatRoom } from "@/lib/chat-api";

/** 레거시 딥링크 — 상대 userId 기준 옛 경로 (웹푸시 구 링크 호환,
 *  docs/specs/chat-language-rooms.md §API). 그 상대와의 방을 조회해
 *  1개면 즉시 리다이렉트, 복수면 방 선택 시트를 보여준다. */
export default function LegacyChatRedirectPage() {
  const { userId } = useParams<{ userId: string }>();
  const peerId = Number(userId);
  const router = useRouter();
  const [rooms, setRooms] = useState<ChatRoom[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(peerId)) return;
    roomsApi
      .list()
      .then((all) => {
        const mine = all.filter((r) => r.peer.id === peerId);
        if (mine.length === 1) {
          router.replace(`/chat/room/${mine[0].id}`);
          return;
        }
        setRooms(mine);
      })
      .catch((e) => setError(e.message));
  }, [peerId, router]);

  if (!Number.isFinite(peerId)) {
    return (
      <main className="p-8">
        <p className="text-sm text-brick-red">잘못된 주소예요</p>
      </main>
    );
  }

  if (rooms === null) {
    return (
      <main className="p-8 text-center text-sm opacity-50">
        {error ?? "불러오는 중..."}
      </main>
    );
  }

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex items-center gap-4">
        <BackLink href="/chat" label="목록" />
        <h1 className="font-hand text-2xl font-bold">
          <span className="hl">방 선택</span>
        </h1>
      </header>

      <div className="mx-auto flex max-w-md flex-col gap-2">
        {rooms.map((r) => (
          <Link
            key={r.id}
            href={`/chat/room/${r.id}`}
            className="flex items-center gap-2 rounded-lg border-2 border-ink/10 bg-white p-3 shadow-sm transition hover:-translate-y-0.5 hover:border-brick-blue/40"
          >
            <b className="truncate">{r.peer.nickname}</b>
            <LangPairBadge source={r.source_lang} target={r.target_lang} mode={r.mode} />
            {r.status === "closed" && (
              <span className="ml-auto shrink-0 text-xs opacity-40">종료</span>
            )}
          </Link>
        ))}
        {rooms.length === 0 && (
          <p className="rounded-lg border-2 border-ink/10 bg-white p-6 text-center text-sm opacity-60">
            아직 이 상대와의 방이 없어요.
            <br />
            <Link href="/chat" className="font-bold text-brick-blue">
              목록
            </Link>
            에서 새로 만들어보세요
          </p>
        )}
      </div>
    </main>
  );
}
