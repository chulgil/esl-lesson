"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { BackLink } from "@/components/nav/BackLink";
import { onChatEvent } from "@/lib/chat-signals";
import { friendsApi, type FriendsList } from "@/lib/friends-api";

/** 친구 — 추가/수락/목록 관리의 단일 진입점 (2026-07-14 IA 정리).
 *  관전은 여기서 "학습 중" 친구를 통해 시작한다 (뷰어: /study/watch). */
export default function FriendsPage() {
  const router = useRouter();
  const [friends, setFriends] = useState<FriendsList | null>(null);
  const [email, setEmail] = useState("");
  const [note, setNote] = useState<string | null>(null);

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
    // 친구 접속/이탈 프레즌스는 WS 로 즉시 반영 (폴링 15초는 학습 중 판별용)
    const off = onChatEvent((msg) => {
      if (msg.t === "presence") refresh();
    });
    return () => {
      clearInterval(timer);
      off();
    };
  }, [refresh]);

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
        <BackLink href="/study" label="학습" />
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">친구</span>
        </h1>
      </header>

      {note && <p className="mb-4 text-sm text-brick-blue">{note}</p>}

      <div className="flex max-w-lg flex-col gap-5">
        {/* 1. 친구 추가 — 가장 먼저 보이게 (신규 사용자 기준) */}
        <section className="rounded-lg border-2 border-ink/10 bg-white p-4">
          <p className="mb-1 text-sm font-bold">친구 추가</p>
          <p className="mb-3 text-xs opacity-60">
            친구의 구글 이메일로 요청을 보내요 — 상대가 수락하면 연결돼요.
          </p>
          <div className="flex items-center gap-2">
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addFriend()}
              placeholder="friend@gmail.com"
              type="email"
              className="min-h-11 flex-1 rounded-md border-2 border-ink/20 px-3 text-sm transition-colors focus:border-brick-blue focus:outline-none"
            />
            <Brick
              color="blue"
              onClick={addFriend}
              className="shrink-0 whitespace-nowrap"
            >
              요청 보내기
            </Brick>
          </div>
        </section>

        {/* 2. 받은 요청 — 응답이 필요한 것 */}
        {friends && friends.incoming.length > 0 && (
          <section className="rounded-lg border-2 border-brick-yellow bg-highlight/20 p-4">
            <p className="mb-2 text-sm font-bold">
              받은 요청 {friends.incoming.length}건
            </p>
            {friends.incoming.map((r) => (
              <div key={r.id} className="flex items-center gap-2 py-1">
                <span className="text-sm font-medium">{r.name}</span>
                <button
                  type="button"
                  onClick={() => friendsApi.accept(r.id).then(refresh)}
                  className="ml-auto min-h-10 rounded-md bg-brick-green px-3 text-sm font-bold text-brick-label transition-colors hover:bg-brick-green/85"
                >
                  수락
                </button>
                <button
                  type="button"
                  onClick={() => friendsApi.decline(r.id).then(refresh)}
                  className="min-h-10 rounded-md border-2 border-ink/20 bg-white px-3 text-sm font-bold"
                >
                  거절
                </button>
              </div>
            ))}
          </section>
        )}

        {/* 3. 내 친구 — 학습 중이면 관전 진입 */}
        <section className="rounded-lg border-2 border-ink/10 bg-white p-4">
          <p className="mb-2 text-sm font-bold">
            내 친구{" "}
            {friends && friends.friends.length > 0 && (
              <span className="font-normal opacity-50">
                {friends.friends.length}명
              </span>
            )}
          </p>
          {friends && friends.friends.length === 0 && (
            <p className="text-sm opacity-50">
              아직 친구가 없어요 — 위에서 이메일로 추가해보세요.
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
                ) : f.online ? (
                  <span className="flex items-center gap-1 rounded-full bg-brick-blue/10 px-2 py-0.5 text-xs font-bold text-brick-blue">
                    <span className="h-1.5 w-1.5 rounded-full bg-brick-green" />
                    접속 중
                  </span>
                ) : (
                  <span className="rounded-full bg-ink/5 px-2 py-0.5 text-xs opacity-50">
                    쉬는 중
                  </span>
                )}
                <span className="ml-auto flex gap-2">
                  <button
                    type="button"
                    onClick={() => router.push(`/chat/${f.user_id}`)}
                    className="min-h-10 rounded-md border-2 border-brick-blue/50 bg-white px-3 text-sm font-bold text-brick-blue transition hover:border-brick-blue"
                  >
                    메시지
                  </button>
                  {f.studying && f.watch_code && (
                    <button
                      type="button"
                      onClick={() =>
                        router.push(`/study/watch?code=${f.watch_code}`)
                      }
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
          {friends && friends.outgoing.length > 0 && (
            <p className="mt-3 text-xs opacity-50">
              수락 대기: {friends.outgoing.map((o) => o.name).join(", ")}
            </p>
          )}
          <p className="mt-3 border-t border-ink/10 pt-3 text-xs opacity-50">
            관전은 친구가 학습 화면에서 [관전 ON]을 켜고, 요청을 수락해야
            시작돼요.
          </p>
        </section>
      </div>
    </main>
  );
}
