"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { fetchMe } from "@/lib/api";
import { GameSocket, type ServerMsg } from "@/lib/game-ws";

const GAME_LABELS: Record<string, string> = {
  tetris: "워드 테트리스",
  quiz: "스피드 퀴즈 로얄",
  typing: "영문 타자연습",
  scramble: "어순 조립 레이스",
  dictation: "받아쓰기 배틀",
};

/** 전역 초대 수신기 — 로그인 시 상시 연결(프레즌스 겸용), 어느 화면에서든 초대 토스트 (P2) */
export function InviteToaster() {
  const router = useRouter();
  const [invite, setInvite] = useState<{
    from: string;
    game: string;
    code: string;
  } | null>(null);

  const handleMessage = useCallback((msg: ServerMsg) => {
    if (msg.t === "iv.invited") {
      setInvite({ from: msg.from, game: msg.game, code: msg.code });
    }
  }, []);

  useEffect(() => {
    let socket: GameSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      socket = new GameSocket(handleMessage, () => {
        retry = setTimeout(connect, 15000); // 프레즌스 유지 — 끊기면 재접속
      });
      socket.connect();
    }
    fetchMe().then((me) => {
      if (me) connect();
    });
    return () => {
      if (retry) clearTimeout(retry);
      socket?.close();
    };
  }, [handleMessage]);

  if (!invite) return null;

  return (
    <div className="fixed inset-x-4 top-16 z-50 mx-auto flex max-w-sm items-center gap-3 rounded-lg border-2 border-brick-green/60 bg-white p-3 shadow-lg">
      <p className="flex-1 text-sm">
        <b>{invite.from}</b> 님이{" "}
        <b>{GAME_LABELS[invite.game] ?? invite.game}</b>에 초대했어요!
      </p>
      <button
        type="button"
        onClick={() => {
          const target = `/game/${invite.game}?join=${invite.code}`;
          setInvite(null);
          router.push(target);
        }}
        className="min-h-10 rounded-md bg-brick-green px-3 text-sm font-bold text-brick-label transition-colors hover:bg-brick-green/85"
      >
        참가
      </button>
      <button
        type="button"
        onClick={() => setInvite(null)}
        aria-label="초대 닫기"
        className="min-h-10 min-w-10 rounded-md text-lg opacity-50 hover:opacity-100"
      >
        ×
      </button>
    </div>
  );
}
