"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { BackLink } from "@/components/nav/BackLink";
import { friendsApi, type FriendsList } from "@/lib/friends-api";
import { GameSocket, type ServerMsg, type StEventPayload } from "@/lib/game-ws";

type Phase = "list" | "requesting" | "watching" | "ended" | "denied";

/** 학습 관전 — 친구 목록에서 학습 중인 친구를 골라 요청, 수락되면 실시간 시청 (study-spectate.md) */
export default function StudyWatchPage() {
  const [friends, setFriends] = useState<FriendsList | null>(null);
  const [email, setEmail] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("list");
  const [hostName, setHostName] = useState("");
  const [event, setEvent] = useState<StEventPayload | null>(null);
  const socketRef = useRef<GameSocket | null>(null);

  const refresh = useCallback(() => {
    friendsApi
      .list()
      .then(setFriends)
      .catch(() =>
        setNote("친구 목록을 불러오지 못했어요 — 로그인 상태를 확인해주세요"),
      );
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 15000); // 학습 중 상태 갱신
    return () => clearInterval(timer);
  }, [refresh]);

  const handleMessage = useCallback((msg: ServerMsg) => {
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
      case "st.end":
        setPhase("ended");
        break;
      case "error":
        setPhase("list");
        setNote(
          msg.code === "room_not_found"
            ? "지금은 관전할 수 없어요 — 친구가 학습을 끝냈거나 관전을 껐어요"
            : msg.code,
        );
        break;
    }
  }, []);

  function watch(code: string) {
    setNote(null);
    setEvent(null);
    socketRef.current?.close();
    const socket = new GameSocket(handleMessage, () => undefined);
    socket.connect();
    socketRef.current = socket;
    setTimeout(() => socket.stRequest(code), 300);
    setPhase("requesting");
  }

  function stopWatching() {
    socketRef.current?.stLeave();
    socketRef.current?.close();
    socketRef.current = null;
    setPhase("list");
    setEvent(null);
    refresh();
  }

  useEffect(() => () => socketRef.current?.close(), []);

  async function addFriend() {
    if (!email.trim()) return;
    setNote(null);
    try {
      await friendsApi.request(email.trim());
      setEmail("");
      setNote("친구 요청을 보냈어요 — 상대가 수락하면 목록에 나타나요");
      refresh();
    } catch (e) {
      const message = e instanceof Error ? e.message : "요청 실패";
      setNote(
        {
          user_not_found: "해당 이메일의 사용자를 찾을 수 없어요",
          already_requested_or_friends: "이미 요청했거나 친구예요",
          cannot_friend_self: "자기 자신은 추가할 수 없어요",
        }[message] ?? message,
      );
    }
  }

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex items-center gap-4">
        <BackLink href="/" label="홈" />
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">학습 관전</span>
        </h1>
      </header>

      {note && <p className="mb-4 text-sm text-brick-blue">{note}</p>}

      {phase === "list" && (
        <section className="flex max-w-lg flex-col gap-6">
          <p className="text-sm opacity-70">
            친구가 학습 중이면 관전을 요청할 수 있어요 — <b>친구가 수락해야</b>{" "}
            화면이 보여요.
          </p>

          <div className="rounded-lg border-2 border-ink/10 bg-white p-4">
            <p className="mb-3 text-sm font-bold">내 친구</p>
            {friends && friends.friends.length === 0 && (
              <p className="text-sm opacity-50">
                아직 친구가 없어요 — 아래에서 이메일로 추가해보세요.
              </p>
            )}
            <ul className="flex flex-col gap-2">
              {friends?.friends.map((f) => (
                <li
                  key={f.user_id}
                  className="flex items-center gap-3 rounded-md border-2 border-ink/10 p-2.5"
                >
                  <span className="font-bold">{f.name}</span>
                  {f.studying ? (
                    <span className="rounded-full bg-brick-green/15 px-2 py-0.5 text-xs font-bold text-brick-green">
                      학습 중
                    </span>
                  ) : (
                    <span className="rounded-full bg-ink/5 px-2 py-0.5 text-xs opacity-50">
                      쉬는 중
                    </span>
                  )}
                  <span className="ml-auto flex gap-2">
                    {f.studying && f.watch_code && (
                      <button
                        type="button"
                        onClick={() => watch(f.watch_code!)}
                        className="min-h-10 rounded-md bg-brick-blue px-3 text-sm font-bold text-brick-label transition-colors hover:bg-brick-blue/85"
                      >
                        관전 요청
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => friendsApi.remove(f.user_id).then(refresh)}
                      className="min-h-10 rounded-md px-2 text-xs opacity-40 hover:opacity-80"
                    >
                      삭제
                    </button>
                  </span>
                </li>
              ))}
            </ul>

            {friends && friends.incoming.length > 0 && (
              <div className="mt-4 border-t border-ink/10 pt-3">
                <p className="mb-2 text-xs font-bold opacity-60">받은 요청</p>
                {friends.incoming.map((r) => (
                  <div key={r.id} className="flex items-center gap-2 py-1">
                    <span className="text-sm">{r.name}</span>
                    <button
                      type="button"
                      onClick={() => friendsApi.accept(r.id).then(refresh)}
                      className="ml-auto min-h-10 rounded-md bg-brick-green px-3 text-sm font-bold text-brick-label"
                    >
                      수락
                    </button>
                    <button
                      type="button"
                      onClick={() => friendsApi.decline(r.id).then(refresh)}
                      className="min-h-10 rounded-md border-2 border-ink/20 px-3 text-sm font-bold"
                    >
                      거절
                    </button>
                  </div>
                ))}
              </div>
            )}

            {friends && friends.outgoing.length > 0 && (
              <p className="mt-3 text-xs opacity-50">
                수락 대기: {friends.outgoing.map((o) => o.name).join(", ")}
              </p>
            )}

            <div className="mt-4 flex items-center gap-2 border-t border-ink/10 pt-4">
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="친구 이메일"
                type="email"
                className="min-h-11 flex-1 rounded-md border-2 border-ink/20 px-3 text-sm transition-colors focus:border-brick-blue focus:outline-none"
              />
              <Brick color="blue" onClick={addFriend}>
                친구 추가
              </Brick>
            </div>
          </div>
        </section>
      )}

      {phase === "requesting" && (
        <section className="flex flex-col items-start gap-4">
          <p className="animate-pulse">
            <b>{hostName || "친구"}</b> 님의 수락을 기다리는 중...
          </p>
          <Brick color="yellow" onClick={stopWatching}>
            취소
          </Brick>
        </section>
      )}

      {phase === "denied" && (
        <section className="flex flex-col items-start gap-4">
          <p>친구가 이번엔 관전을 거절했어요 — 다음에 다시 요청해보세요.</p>
          <Brick color="blue" onClick={stopWatching}>
            목록으로
          </Brick>
        </section>
      )}

      {phase === "ended" && (
        <section className="flex flex-col items-start gap-4">
          <p>
            <b>{hostName}</b> 님의 학습이 끝났어요. 수고 박수!
          </p>
          <Brick color="blue" onClick={stopWatching}>
            목록으로
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
                {String(event.answered_count)}문항 중{" "}
                {String(event.correct_count)}개 정답
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

          <div>
            <Brick color="yellow" onClick={stopWatching}>
              관전 종료
            </Brick>
          </div>
        </section>
      )}
    </main>
  );
}
