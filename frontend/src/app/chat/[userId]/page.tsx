"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { KaomojiPicker } from "@/components/chat/KaomojiPicker";
import { WordSharePicker } from "@/components/chat/WordSharePicker";
import { BackLink } from "@/components/nav/BackLink";
import { fetchMe } from "@/lib/api";
import {
  chatApi,
  newClientMsgId,
  type ChatMessage,
  type ShareableItem,
} from "@/lib/chat-api";
import { dispatchChatEvent, onChatEvent, sendTyping } from "@/lib/chat-signals";

/** 대화방 — 무한스크롤·읽음 "1"·입력중·카오모지·단어 카드 (docs/specs/chat.md) */

// 대화별 메모리 캐시 — 뒤로가기 후 재진입 시 즉시 복원 (스펙: 클라이언트 캐싱)
const roomCache = new Map<number, ChatMessage[]>();

interface Pending {
  client_msg_id: string;
  body: string;
  item: ShareableItem | null;
  failed: boolean;
}

export default function ChatRoomPage() {
  const { userId } = useParams<{ userId: string }>();
  const otherId = Number(userId);

  const [myId, setMyId] = useState<number | null>(null);
  const [peerName, setPeerName] = useState("");
  const [online, setOnline] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(
    () => roomCache.get(otherId) ?? [],
  );
  const [otherRead, setOtherRead] = useState(0);
  const [typing, setTyping] = useState(false);
  const [pending, setPending] = useState<Pending[]>([]);
  const [input, setInput] = useState("");
  const [attachedItem, setAttachedItem] = useState<ShareableItem | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const listRef = useRef<HTMLDivElement>(null);
  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stickBottom = useRef(true);

  // 메시지 갱신 시 캐시 동기화
  useEffect(() => {
    if (messages.length > 0) roomCache.set(otherId, messages.slice(-100));
  }, [messages, otherId]);

  const scrollToBottom = useCallback(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  // 초기 로드 — 최신 50개 + 읽음 위치 + 상대 정보, 진입 즉시 읽음 처리
  useEffect(() => {
    if (!Number.isFinite(otherId)) return;
    fetchMe().then((me) => me && setMyId(me.id));
    chatApi
      .messages(otherId)
      .then((res) => {
        setMessages(res.items);
        setOnline(res.online);
        if (res.peer) setPeerName(res.peer.name);
        const reads = res.reads[String(otherId)];
        if (reads) setOtherRead(reads);
        setHasMore(res.items.length >= 50);
        chatApi
          .markRead(otherId)
          .then(() =>
            dispatchChatEvent({
              t: "chat.read",
              conversation_id: 0,
              user_id: 0, // 내 읽음 — 배지 갱신 트리거용 로컬 신호
              last_read_message_id: 0,
            }),
          )
          .catch(() => {});
        requestAnimationFrame(scrollToBottom);
      })
      .catch((e) => setError(e.message));
  }, [otherId, scrollToBottom]);

  // WS 이벤트 구독 — 수신·읽음·입력중·프레즌스
  useEffect(() => {
    return onChatEvent((msg) => {
      if (msg.t === "chat.message" && msg.sender_id === otherId) {
        setMessages((prev) =>
          prev.some((m) => m.id === msg.id) ? prev : [...prev, msg],
        );
        setTyping(false);
        chatApi
          .markRead(otherId)
          .then(() =>
            dispatchChatEvent({
              t: "chat.read",
              conversation_id: 0,
              user_id: 0,
              last_read_message_id: 0,
            }),
          )
          .catch(() => {});
        if (stickBottom.current) requestAnimationFrame(scrollToBottom);
      } else if (msg.t === "chat.read" && msg.user_id === otherId) {
        setOtherRead(msg.last_read_message_id);
      } else if (msg.t === "chat.typing" && msg.from_user_id === otherId) {
        setTyping(true);
        if (typingTimer.current) clearTimeout(typingTimer.current);
        typingTimer.current = setTimeout(() => setTyping(false), 5000);
      } else if (msg.t === "presence" && msg.user_id === otherId) {
        setOnline(msg.online);
      }
    });
  }, [otherId, scrollToBottom]);

  // 위로 무한스크롤 (before 커서)
  const loadOlder = useCallback(async () => {
    const oldest = messages[0];
    if (!oldest || !hasMore) return;
    const el = listRef.current;
    const prevHeight = el?.scrollHeight ?? 0;
    const res = await chatApi.messages(otherId, oldest.id);
    setMessages((prev) => [...res.items, ...prev]);
    setHasMore(res.items.length >= 50);
    // 스크롤 위치 유지 — 로드 전 첫 항목이 그대로 보이게
    requestAnimationFrame(() => {
      if (el) el.scrollTop = el.scrollHeight - prevHeight;
    });
  }, [messages, hasMore, otherId]);

  function onScroll() {
    const el = listRef.current;
    if (!el) return;
    stickBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (el.scrollTop < 60 && hasMore) loadOlder();
  }

  // 전송 — 낙관적 렌더 → 확정 치환, 실패 시 재시도 (스펙: 클라이언트 캐싱)
  async function send(pendingEntry?: Pending) {
    const body = pendingEntry?.body ?? input.trim();
    const item = pendingEntry?.item ?? attachedItem;
    if (!body && !item) return;
    const client_msg_id = pendingEntry?.client_msg_id ?? newClientMsgId();

    if (!pendingEntry) {
      setInput("");
      setAttachedItem(null);
      setPending((prev) => [
        ...prev,
        { client_msg_id, body, item, failed: false },
      ]);
      requestAnimationFrame(scrollToBottom);
    } else {
      setPending((prev) =>
        prev.map((p) =>
          p.client_msg_id === client_msg_id ? { ...p, failed: false } : p,
        ),
      );
    }

    try {
      const saved = await chatApi.send({
        to_user_id: otherId,
        body,
        client_msg_id,
        item_id: item?.id,
      });
      setPending((prev) =>
        prev.filter((p) => p.client_msg_id !== client_msg_id),
      );
      setMessages((prev) =>
        prev.some((m) => m.id === saved.id) ? prev : [...prev, saved],
      );
      if (stickBottom.current) requestAnimationFrame(scrollToBottom);
    } catch (e) {
      setPending((prev) =>
        prev.map((p) =>
          p.client_msg_id === client_msg_id ? { ...p, failed: true } : p,
        ),
      );
      if (e instanceof Error && e.message === "not_friends") {
        setError("친구 관계가 아니에요 — 다시 친구를 맺으면 보낼 수 있어요");
      }
    }
  }

  if (!Number.isFinite(otherId)) {
    return (
      <main className="p-8">
        <p className="text-sm text-brick-red">잘못된 주소예요</p>
      </main>
    );
  }

  return (
    <main className="notebook-lines notebook-margin flex h-dvh flex-col px-4 py-4 sm:px-16 sm:py-6">
      <header className="mb-3 flex items-center gap-3">
        <BackLink href="/chat" label="채팅" />
        <h1 className="flex items-center gap-2 font-hand text-2xl font-bold">
          <span className="hl">{peerName || "..."}</span>
          <span
            aria-label={online ? "접속 중" : "미접속"}
            title={online ? "접속 중" : "미접속"}
            className={`h-3 w-3 rounded-full ${
              online ? "bg-brick-green" : "bg-ink/20"
            }`}
          />
        </h1>
      </header>

      {error && <p className="mb-2 text-sm text-brick-red">{error}</p>}

      {/* 메시지 목록 */}
      <div
        ref={listRef}
        onScroll={onScroll}
        className="flex-1 overflow-y-auto rounded-lg border-2 border-ink/10 bg-white/70 p-3"
      >
        {hasMore && messages.length > 0 && (
          <p className="py-2 text-center text-xs opacity-40">
            위로 스크롤하면 이전 대화를 불러와요
          </p>
        )}
        {messages.map((m) => (
          <Bubble
            key={m.id}
            msg={m}
            mine={m.sender_id === myId}
            unreadByOther={m.sender_id === myId && m.id > otherRead}
          />
        ))}
        {pending.map((p) => (
          <PendingBubble
            key={p.client_msg_id}
            entry={p}
            onRetry={() => send(p)}
          />
        ))}
        {typing && (
          <p className="mt-1 px-2 text-xs opacity-50">
            {peerName} 입력 중{" "}
            <span className="inline-block animate-pulse">···</span>
          </p>
        )}
        {messages.length === 0 && pending.length === 0 && (
          <p className="py-10 text-center text-sm opacity-40">
            첫 메시지를 보내보세요 (´｡• ᵕ •｡`)
          </p>
        )}
      </div>

      {/* 첨부된 단어 카드 미리보기 */}
      {attachedItem && (
        <div className="mt-2 flex items-center gap-2 rounded-md border-2 border-brick-yellow/60 bg-highlight/30 px-3 py-1.5 text-sm">
          <b>{attachedItem.en_text}</b>
          <span className="opacity-60">{attachedItem.ko_text}</span>
          <button
            type="button"
            onClick={() => setAttachedItem(null)}
            aria-label="첨부 해제"
            className="ml-auto opacity-50 hover:opacity-100"
          >
            ×
          </button>
        </div>
      )}

      {/* 입력줄 */}
      <div className="mt-2 flex items-end gap-1.5">
        <WordSharePicker onPick={setAttachedItem} />
        <KaomojiPicker onPick={(k) => setInput((v) => v + k)} />
        <input
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            sendTyping(otherId); // 클라 3초 스로틀 내장
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing) send();
          }}
          placeholder="메시지 입력..."
          maxLength={2000}
          className="min-h-11 flex-1 rounded-md border-2 border-ink/20 px-3 text-sm transition-colors focus:border-brick-blue focus:outline-none"
        />
        <button
          type="button"
          onClick={() => send()}
          disabled={!input.trim() && !attachedItem}
          className="min-h-11 rounded-md bg-brick-blue px-4 text-sm font-bold text-brick-label transition-colors hover:bg-brick-blue/85 disabled:opacity-40"
        >
          보내기
        </button>
      </div>
    </main>
  );
}

function Bubble({
  msg,
  mine,
  unreadByOther,
}: {
  msg: ChatMessage;
  mine: boolean;
  unreadByOther: boolean;
}) {
  return (
    <div className={`mb-1.5 flex ${mine ? "justify-end" : "justify-start"}`}>
      {/* 읽음 전 "1" — 카카오톡 관례 (스펙: 읽음 표시) */}
      {mine && unreadByOther && (
        <span className="mr-1 self-end text-xs font-bold text-brick-yellow">
          1
        </span>
      )}
      <div
        className={`max-w-[75%] rounded-xl border-2 px-3 py-1.5 text-sm ${
          mine
            ? "border-brick-blue/30 bg-brick-blue/10"
            : "border-ink/10 bg-white"
        }`}
      >
        {msg.item_ref && (
          <span className="mb-1 block rounded-md border-2 border-brick-yellow/50 bg-highlight/40 px-2 py-1">
            <b>{msg.item_ref.en_text}</b>
            <span className="ml-2 text-xs opacity-70">
              {msg.item_ref.ko_text}
            </span>
          </span>
        )}
        {msg.body && (
          <span className="break-words whitespace-pre-wrap">{msg.body}</span>
        )}
        {msg.created_at && (
          <span className="mt-0.5 block text-right text-[10px] opacity-40">
            {new Date(msg.created_at).toLocaleTimeString("ko-KR", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
      </div>
    </div>
  );
}

function PendingBubble({
  entry,
  onRetry,
}: {
  entry: Pending;
  onRetry: () => void;
}) {
  return (
    <div className="mb-1.5 flex justify-end">
      <div className="max-w-[75%] rounded-xl border-2 border-brick-blue/20 bg-brick-blue/5 px-3 py-1.5 text-sm opacity-70">
        {entry.item && (
          <span className="mb-1 block rounded-md border-2 border-brick-yellow/40 bg-highlight/30 px-2 py-1">
            <b>{entry.item.en_text}</b>
          </span>
        )}
        {entry.body && <span className="break-words">{entry.body}</span>}
        {entry.failed ? (
          <button
            type="button"
            onClick={onRetry}
            className="mt-0.5 block text-right text-[11px] font-bold text-brick-red"
          >
            전송 실패 — 다시 시도
          </button>
        ) : (
          <span className="mt-0.5 block text-right text-[10px] opacity-50">
            보내는 중...
          </span>
        )}
      </div>
    </div>
  );
}
