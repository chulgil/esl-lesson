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
  const offline = friends.filter((f) => !f.online);
  if (friends.length === 0) return null;

  return (
    <div className="w-full">
      <p className="mb-2 text-xs font-bold opacity-60">친구 초대</p>
      <div className="flex flex-wrap gap-2">
        {online.map((f) => (
          <InviteButton
            key={f.user_id}
            friend={f}
            sent={sent.has(f.user_id)}
            onInvite={() => {
              onInvite(f.user_id);
              setSent((prev) => new Set(prev).add(f.user_id));
            }}
          />
        ))}
        {/* 접속 중이 아닌 친구 — 웹 푸시 초대장으로 도달 */}
        {offline.map((f) => (
          <InviteButton
            key={f.user_id}
            friend={f}
            offline
            sent={sent.has(f.user_id)}
            onInvite={() => {
              onInvite(f.user_id);
              setSent((prev) => new Set(prev).add(f.user_id));
            }}
          />
        ))}
      </div>
      {offline.length > 0 && (
        <p className="mt-2 text-xs opacity-50">
          접속 중이 아닌 친구에게는 알림으로 초대장이 가요 — 방 코드를 직접
          알려줘도 돼요.
        </p>
      )}
    </div>
  );
}

function InviteButton({
  friend,
  sent,
  offline = false,
  onInvite,
}: {
  friend: FriendEntry;
  sent: boolean;
  offline?: boolean;
  onInvite: () => void;
}) {
  return (
    <button
      type="button"
      disabled={sent}
      onClick={onInvite}
      className={`min-h-10 rounded-full border-2 bg-white px-3 text-sm font-bold transition active:scale-95 disabled:opacity-60 ${
        offline
          ? "border-ink/20 opacity-80 hover:border-ink/40"
          : "border-brick-green/50 hover:border-brick-green"
      }`}
    >
      {sent
        ? `${friend.name} — 초대 보냄`
        : offline
          ? `${friend.name} 알림 초대`
          : `${friend.name} 초대`}
    </button>
  );
}
