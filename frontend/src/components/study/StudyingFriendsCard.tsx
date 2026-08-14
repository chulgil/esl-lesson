"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { onChatEvent } from "@/lib/chat-signals";
import { friendsApi, type FriendEntry } from "@/lib/friends-api";

const POLL_MS = 60000;

/** 지금 학습 중인 친구 카드 — 홈/학습 탭 공용 관전 진입점
 *  (docs/specs/study-spectate.md §진입 경로 재설계 2026-08-14).
 *  GET /api/friends 의 studying·watch_code 를 재사용 — 학습 중인 친구가
 *  없으면 카드 자체를 숨긴다. */
export function StudyingFriendsCard() {
  const [friends, setFriends] = useState<FriendEntry[] | null>(null);

  useEffect(() => {
    const refresh = () => {
      friendsApi
        .list()
        .then((res) => setFriends(res.friends))
        .catch(() => undefined);
    };
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    // 접속 프레즌스 이벤트로도 즉시 갱신 (/friends 페이지와 동일 패턴)
    const off = onChatEvent((msg) => {
      if (msg.t === "presence") refresh();
    });
    return () => {
      clearInterval(timer);
      off();
    };
  }, []);

  const studying = (friends ?? []).filter((f) => f.studying && f.watch_code);
  if (studying.length === 0) return null;

  return (
    <section className="max-w-xl rounded-lg border-2 border-brick-green/40 bg-white p-4">
      <p className="mb-2 text-sm font-bold">지금 학습 중인 친구</p>
      <ul className="flex flex-col gap-2">
        {studying.map((f) => (
          <li
            key={f.user_id}
            className="flex items-center gap-2 rounded-md border-2 border-ink/10 p-2.5"
          >
            <span className="font-bold">{f.name}</span>
            <span className="flex items-center gap-1 rounded-full bg-brick-green/15 px-2 py-0.5 text-xs font-bold text-brick-green">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brick-green" />
              학습 중
            </span>
            <Link
              href={`/study/watch?code=${f.watch_code}`}
              className="ml-auto inline-flex min-h-10 items-center rounded-md bg-brick-green px-3 text-sm font-bold text-brick-label transition-colors hover:bg-brick-green/85"
            >
              관전
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
