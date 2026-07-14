"use client";

import { useEffect, useState } from "react";
import { friendsApi, type FriendEntry } from "@/lib/friends-api";

/** 대기실 친구 초대 — 접속 중인 친구에게 원탭 초대 (P2 경쟁 루프) */
export function InviteFriends({
  onInvite,
}: {
  onInvite: (userId: number) => void;
}) {
  const [friends, setFriends] = useState<FriendEntry[]>([]);
  const [sent, setSent] = useState<Set<number>>(new Set());

  useEffect(() => {
    friendsApi
      .list()
      .then((res) => setFriends(res.friends))
      .catch(() => undefined);
  }, []);

  const online = friends.filter((f) => f.online);
  if (friends.length === 0) return null;

  return (
    <div className="w-full">
      <p className="mb-2 text-xs font-bold opacity-60">친구 초대</p>
      {online.length === 0 ? (
        <p className="text-xs opacity-50">
          지금 접속 중인 친구가 없어요 — 방 코드를 직접 알려줘도 돼요.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {online.map((f) => (
            <button
              key={f.user_id}
              type="button"
              disabled={sent.has(f.user_id)}
              onClick={() => {
                onInvite(f.user_id);
                setSent((prev) => new Set(prev).add(f.user_id));
              }}
              className="min-h-10 rounded-full border-2 border-brick-green/50 bg-white px-3 text-sm font-bold transition hover:border-brick-green active:scale-95 disabled:opacity-60"
            >
              {sent.has(f.user_id) ? `${f.name} — 초대 보냄` : `${f.name} 초대`}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
