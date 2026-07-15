"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FloatingCheers,
  useFloatingCheers,
} from "@/components/study/FloatingCheers";
import { GameSocket, type ServerMsg, type StEventPayload } from "@/lib/game-ws";

/** 학습 관전 호스트 — 허용 토글 + 관전 요청 수락/거절 (승인제, study-spectate.md).
 *  snapshot 이 바뀔 때마다 수락된 관전자에게 화면 상태를 릴레이한다. */
export function SpectateHost({
  snapshot,
}: {
  snapshot: StEventPayload | null;
}) {
  const [enabled, setEnabled] = useState(false);
  const [code, setCode] = useState<string | null>(null);
  const [requests, setRequests] = useState<
    { watcher_id: number; name: string }[]
  >([]);
  const [watcherNote, setWatcherNote] = useState<string | null>(null);
  const socketRef = useRef<GameSocket | null>(null);
  const lastSentRef = useRef<string>("");
  // 관전자 응원·채팅 — 떠오르며 사라지는 오버레이 (집중 보호, 입력 없음)
  const { items: cheers, push: pushCheer } = useFloatingCheers();

  const handleMessage = useCallback(
    (msg: ServerMsg) => {
      switch (msg.t) {
        case "st.hosting":
          setCode(msg.code);
          break;
        case "st.request":
          setRequests((prev) =>
            prev.some((r) => r.watcher_id === msg.watcher_id)
              ? prev
              : [...prev, { watcher_id: msg.watcher_id, name: msg.name }],
          );
          break;
        case "st.chat":
          pushCheer({ name: msg.name, text: msg.text });
          break;
        case "st.cheer":
          pushCheer({ name: msg.name, kind: msg.kind });
          break;
        case "st.left":
          setWatcherNote(`${msg.name} 님이 관전을 종료했어요`);
          setTimeout(() => setWatcherNote(null), 3000);
          break;
      }
    },
    [pushCheer],
  );

  // 토글 on → 연결 + 호스팅, off → 정리
  useEffect(() => {
    if (!enabled) return;
    const socket = new GameSocket(handleMessage, () => setCode(null));
    socket.connect();
    socketRef.current = socket;
    const timer = setTimeout(() => socket.stHost(), 300); // 연결 안정 대기
    return () => {
      clearTimeout(timer);
      socket.stLeave();
      socket.close();
      socketRef.current = null;
      setCode(null);
      setRequests([]);
    };
  }, [enabled, handleMessage]);

  // 화면 상태 릴레이 — 수락된 관전자에게만 전달됨 (서버가 필터)
  useEffect(() => {
    if (!enabled || !code || !snapshot) return;
    const serialized = JSON.stringify(snapshot);
    if (serialized === lastSentRef.current) return;
    lastSentRef.current = serialized;
    socketRef.current?.stEvent(snapshot);
  }, [enabled, code, snapshot]);

  function decide(watcherId: number, allow: boolean) {
    socketRef.current?.stAllow(watcherId, allow);
    setRequests((prev) => prev.filter((r) => r.watcher_id !== watcherId));
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setEnabled((v) => !v)}
        aria-pressed={enabled}
        title="친구가 내 학습을 관전할 수 있게 허용 (요청마다 수락 필요)"
        className={`inline-flex min-h-11 items-center gap-2 rounded-md border-2 px-3 text-sm font-bold shadow-sm transition ${
          enabled
            ? "border-brick-green bg-brick-green/10 text-brick-green"
            : "border-ink/25 bg-white hover:border-brick-green"
        }`}
      >
        관전 {enabled ? "ON" : "OFF"}
        {enabled && code && (
          <span className="rounded bg-highlight/60 px-1.5 font-mono text-xs text-ink">
            {code}
          </span>
        )}
      </button>

      {/* 관전 요청 수락 프롬프트 — 학습 흐름 위에 떠서 바로 결정 */}
      {requests.length > 0 && (
        <div className="fixed inset-x-4 top-16 z-50 mx-auto flex max-w-sm flex-col gap-2">
          {requests.map((r) => (
            <div
              key={r.watcher_id}
              className="flex items-center gap-3 rounded-lg border-2 border-brick-blue/50 bg-white p-3 shadow-lg"
            >
              <p className="flex-1 text-sm">
                <b>{r.name}</b> 님이 관전을 요청했어요
              </p>
              <button
                type="button"
                onClick={() => decide(r.watcher_id, true)}
                className="min-h-10 rounded-md bg-brick-green px-3 text-sm font-bold text-brick-label"
              >
                수락
              </button>
              <button
                type="button"
                onClick={() => decide(r.watcher_id, false)}
                className="min-h-10 rounded-md border-2 border-ink/20 bg-white px-3 text-sm font-bold"
              >
                거절
              </button>
            </div>
          ))}
        </div>
      )}

      {watcherNote && (
        <p className="fixed inset-x-4 top-16 z-50 mx-auto max-w-sm rounded-lg bg-ink/80 p-2 text-center text-xs text-white">
          {watcherNote}
        </p>
      )}

      <FloatingCheers items={cheers} />
    </>
  );
}
