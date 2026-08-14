"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { friendsApi } from "@/lib/friends-api";

/** 상대가 지금 학습 중이면 관전 진입 배지 — 방 목록·대화방 헤더 공용
 *  (docs/specs/study-spectate.md §진입 경로 #3 "채팅에서"). 관전 ON(opt-in) 인
 *  학습자만 studying=true 로 노출되므로 여기서도 그대로 따른다. */
export function StudyingBadge({
  peerId,
  variant = "note",
}: {
  peerId: number | null;
  variant?: "note" | "excel";
}) {
  const router = useRouter();
  const [code, setCode] = useState<string | null>(null);

  useEffect(() => {
    if (peerId == null) return;
    let alive = true;
    friendsApi
      .list()
      .then((res) => {
        if (!alive) return;
        const friend = res.friends.find((f) => f.user_id === peerId);
        setCode(friend?.studying ? friend.watch_code : null);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [peerId]);

  if (!code) return null;

  return (
    <button
      type="button"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        router.push(`/study/watch?code=${code}`);
      }}
      className={
        variant === "excel"
          ? "shrink-0 rounded-sm border border-[#217346] bg-[#e2efda] px-1.5 py-0.5 text-[10px] font-bold text-[#217346]"
          : "shrink-0 rounded-full border-2 border-brick-green/50 bg-brick-green/10 px-2 py-0.5 text-[10px] font-bold text-brick-green"
      }
    >
      학습 중 · 관전
    </button>
  );
}
