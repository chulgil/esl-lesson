"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { BackLink } from "@/components/nav/BackLink";
import {
  CHEER_KINDS,
  CheerIcon,
  FloatingCheers,
  useFloatingCheers,
} from "@/components/study/FloatingCheers";
import { GameSocket, type ServerMsg, type StEventPayload } from "@/lib/game-ws";

type Phase = "idle" | "requesting" | "watching" | "ended" | "denied";

export default function StudyWatchPage() {
  return (
    <Suspense>
      <WatchInner />
    </Suspense>
  );
}

/** 관전 뷰어 — 친구 페이지에서 진입 (?code=), 수락되면 실시간 시청 (study-spectate.md) */
function WatchInner() {
  const params = useSearchParams();
  const code = params.get("code");
  const [phase, setPhase] = useState<Phase>("idle");
  const [hostName, setHostName] = useState("");
  const [event, setEvent] = useState<StEventPayload | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [chat, setChat] = useState("");
  const socketRef = useRef<GameSocket | null>(null);
  const { items: cheers, push: pushCheer } = useFloatingCheers();

  const handleMessage = useCallback(
    (msg: ServerMsg) => {
      switch (msg.t) {
        case "st.requested":
          setHostName(msg.host);
          setPhase("requesting");
          break;
        case "st.approved":
          setHostName(msg.host);
          setPhase("watching");
          break;
        case "st.denied":
          setPhase("denied");
          break;
        case "st.event":
          setEvent(msg.payload);
          break;
        case "st.chat":
          pushCheer({ name: msg.name, text: msg.text });
          break;
        case "st.cheer":
          pushCheer({ name: msg.name, kind: msg.kind });
          break;
        case "st.end":
          setPhase("ended");
          break;
        case "error":
          setPhase("idle");
          setNote(
            msg.code === "room_not_found"
              ? "지금은 관전할 수 없어요 — 친구가 학습을 끝냈거나 관전을 껐어요"
              : msg.code,
          );
          break;
      }
    },
    [pushCheer],
  );

  function sendChat() {
    const text = chat.trim();
    if (!text) return;
    socketRef.current?.stChat(text);
    setChat("");
  }

  // 친구 페이지에서 ?code= 로 진입 → 자동 관전 요청
  useEffect(() => {
    if (!code) return;
    const socket = new GameSocket(handleMessage, () => undefined);
    socket.connect();
    socketRef.current = socket;
    const timer = setTimeout(() => socket.stRequest(code), 300);
    setPhase("requesting");
    return () => {
      clearTimeout(timer);
      socket.stLeave();
      socket.close();
      socketRef.current = null;
    };
  }, [code, handleMessage]);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex items-center gap-4">
        <BackLink href="/friends" label="친구" />
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">학습 관전</span>
        </h1>
      </header>

      {note && <p className="mb-4 text-sm text-brick-blue">{note}</p>}

      {(phase === "idle" || !code) && (
        <section className="flex flex-col items-start gap-4">
          {!note && (
            <p className="text-sm opacity-70">
              관전은 <b>친구 페이지</b>에서 학습 중인 친구를 골라 시작해요.
            </p>
          )}
          <Brick color="blue" href="/friends">
            친구 목록으로
          </Brick>
        </section>
      )}

      {phase === "requesting" && (
        <section className="flex flex-col items-start gap-4">
          <p className="animate-pulse">
            <b>{hostName || "친구"}</b> 님의 수락을 기다리는 중...
          </p>
          <Brick color="yellow" href="/friends">
            취소
          </Brick>
        </section>
      )}

      {phase === "denied" && (
        <section className="flex flex-col items-start gap-4">
          <p>친구가 이번엔 관전을 거절했어요 — 다음에 다시 요청해보세요.</p>
          <Brick color="blue" href="/friends">
            친구 목록으로
          </Brick>
        </section>
      )}

      {phase === "ended" && (
        <section className="flex flex-col items-start gap-4">
          <p>
            <b>{hostName}</b> 님의 학습이 끝났어요. 수고 박수!
          </p>
          <Brick color="blue" href="/friends">
            친구 목록으로
          </Brick>
        </section>
      )}

      {phase === "watching" && (
        <section className="flex max-w-xl flex-col gap-4">
          <p className="text-sm">
            <span className="rounded-full bg-brick-red/10 px-2 py-0.5 text-xs font-bold text-brick-red">
              LIVE
            </span>{" "}
            <b>{hostName}</b> 님 학습 관전 중
            {typeof event?.index === "number" && (
              <span className="ml-2 opacity-60">
                {event.index}/{event.total} 문항 · 정답 {event.correct_count}개
              </span>
            )}
          </p>

          {!event && (
            <p className="text-sm opacity-50">화면을 기다리는 중...</p>
          )}

          {event && event.phase === "done" && (
            <div className="rounded-lg border-2 border-brick-green/50 bg-white p-5">
              <p className="font-hand text-2xl font-bold">세션 완료!</p>
              <p className="mt-1 text-sm opacity-70">
                {event.answered_count}문항 중 {event.correct_count}개 정답
              </p>
            </div>
          )}

          {event && event.phase !== "done" && (
            <div className="rounded-lg border-2 border-ink/10 bg-white p-6">
              <p className="text-2xl font-bold">{event.prompt}</p>
              {event.prompt_ko && (
                <p className="mt-1 text-sm opacity-60">{event.prompt_ko}</p>
              )}
              {event.template && (
                <p className="mt-1 font-mono text-sm opacity-60">
                  {event.template}
                </p>
              )}
              {Array.isArray(event.choices) && (
                <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {event.choices.map((choice) => {
                    const isAnswer =
                      event.phase === "feedback" &&
                      event.result?.correct_answer === choice;
                    return (
                      <div
                        key={choice}
                        className={`rounded-md border-2 px-3 py-2 text-sm ${
                          isAnswer
                            ? "border-brick-green bg-brick-green/10 font-bold"
                            : "border-ink/10"
                        }`}
                      >
                        {choice}
                      </div>
                    );
                  })}
                </div>
              )}
              {event.phase === "feedback" && event.result != null && (
                <p
                  className={`mt-3 font-bold ${
                    event.result.correct ? "text-brick-green" : "text-brick-red"
                  }`}
                >
                  {event.result.correct ? "정답!" : "오답"}
                </p>
              )}
            </div>
          )}

          {/* 응원 보내기 — 아프리카TV 별풍선처럼 원탭, 서버가 도배 방지 스로틀 */}
          <div className="flex flex-wrap items-center gap-2">
            {CHEER_KINDS.map((c) => (
              <button
                key={c.kind}
                type="button"
                onClick={() => socketRef.current?.stCheer(c.kind)}
                className="flex min-h-11 cursor-pointer items-center gap-1.5 rounded-full border-2 border-ink/15 bg-white px-3 text-sm font-bold transition hover:-translate-y-0.5 hover:border-ink/40 active:translate-y-0"
              >
                <CheerIcon kind={c.kind} />
                {c.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <input
              value={chat}
              onChange={(e) => setChat(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendChat()}
              maxLength={100}
              placeholder="응원 한마디 (친구 화면에 떠올라요)"
              className="min-h-11 flex-1 rounded-md border-2 border-ink/20 bg-white px-3 text-sm transition-colors focus:border-brick-blue focus:outline-none"
            />
            <button
              type="button"
              onClick={sendChat}
              className="min-h-11 shrink-0 rounded-md border-2 border-ink/20 bg-white px-4 text-sm font-bold whitespace-nowrap transition hover:border-ink/50"
            >
              보내기
            </button>
          </div>

          <div>
            <Brick color="yellow" href="/friends">
              관전 종료
            </Brick>
          </div>
        </section>
      )}

      <FloatingCheers items={cheers} />
    </main>
  );
}
