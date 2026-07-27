"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { PendingMessage } from "@/components/chat/skins/types";
import { fetchMe } from "@/lib/api";
import { prepareImageForUpload, UnsupportedImageError } from "@/lib/image-utils";
import {
  chatApi,
  newClientMsgId,
  type ChatMessage,
  type ShareableItem,
} from "@/lib/chat-api";
import {
  dispatchChatEvent,
  onChatEvent,
  sendTyping,
  setActiveChatRoom,
} from "@/lib/chat-signals";

/** 대화방 데이터·동작 훅 — 전체 페이지와 플로팅 위젯이 공유 (docs/specs/chat.md).
 *  표현(스킨)은 반환된 상태·핸들러만 사용한다. */

// 대화별 메모리 캐시 — 재진입 시 즉시 복원 (스펙: 클라이언트 캐싱)
const roomCache = new Map<number, ChatMessage[]>();

export interface AttachedImage {
  url: string; // 로컬 미리보기 (objectURL)
  imageId: string | null; // 업로드 완료 후 서버 파일명
  uploading: boolean;
}

export function useChatRoom(otherId: number) {
  const [myId, setMyId] = useState<number | null>(null);
  const [peerName, setPeerName] = useState("");
  const [online, setOnline] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(
    () => roomCache.get(otherId) ?? [],
  );
  const [otherRead, setOtherRead] = useState(0);
  const [typing, setTyping] = useState(false);
  const [pending, setPending] = useState<PendingMessage[]>([]);
  const [input, setInput] = useState("");
  const [attachedItem, setAttachedItem] = useState<ShareableItem | null>(null);
  const [attachedImage, setAttachedImage] = useState<AttachedImage | null>(
    null,
  );
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const listRef = useRef<HTMLDivElement>(null);
  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stickBottom = useRef(true);

  useEffect(() => {
    if (messages.length > 0) roomCache.set(otherId, messages.slice(-100));
  }, [messages, otherId]);

  // 보고 있는 대화 등록 — 전역 토스트·OS 알림 중복 억제 (위젯과 동일 경로)
  useEffect(() => {
    setActiveChatRoom(otherId);
    return () => setActiveChatRoom(null);
  }, [otherId]);

  const scrollToBottom = useCallback(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  const markReadAndSignal = useCallback(() => {
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
  }, [otherId]);

  // 초기 로드
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
        markReadAndSignal();
        requestAnimationFrame(scrollToBottom);
      })
      .catch((e) => setError(e.message));
  }, [otherId, scrollToBottom, markReadAndSignal]);

  // WS 이벤트 구독
  useEffect(() => {
    return onChatEvent((msg) => {
      if (msg.t === "chat.message" && msg.sender_id === otherId) {
        setMessages((prev) =>
          prev.some((m) => m.id === msg.id) ? prev : [...prev, msg],
        );
        setTyping(false);
        markReadAndSignal();
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
  }, [otherId, scrollToBottom, markReadAndSignal]);

  // 위로 무한스크롤
  const loadOlder = useCallback(async () => {
    const oldest = messages[0];
    if (!oldest || !hasMore) return;
    const el = listRef.current;
    const prevHeight = el?.scrollHeight ?? 0;
    const res = await chatApi.messages(otherId, oldest.id);
    setMessages((prev) => [...res.items, ...prev]);
    setHasMore(res.items.length >= 50);
    requestAnimationFrame(() => {
      if (el) el.scrollTop = el.scrollHeight - prevHeight;
    });
  }, [messages, hasMore, otherId]);

  const onScroll = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    stickBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (el.scrollTop < 60 && hasMore) loadOlder();
  }, [hasMore, loadOlder]);

  // 이미지 첨부 — 큰 사진·미지원 형식은 자동 변환 후 업로드 (image-utils)
  const onAttachImageFile = useCallback(async (file: File) => {
    setError(null);
    let prepared: File;
    try {
      prepared = await prepareImageForUpload(file);
    } catch (e) {
      setError(
        e instanceof UnsupportedImageError
          ? "이 형식은 보낼 수 없어요 — jpg·png·webp·gif 로 저장해서 다시 시도해주세요"
          : "이미지를 준비하지 못했어요 — 다른 사진으로 시도해주세요",
      );
      return;
    }
    const url = URL.createObjectURL(prepared);
    setAttachedImage({ url, imageId: null, uploading: true });
    chatApi
      .uploadImage(prepared)
      .then((res) =>
        setAttachedImage((prev) =>
          prev && prev.url === url
            ? { ...prev, imageId: res.image_id, uploading: false }
            : prev,
        ),
      )
      .catch((e) => {
        setAttachedImage(null);
        URL.revokeObjectURL(url);
        const detail = e instanceof Error ? e.message : "";
        setError(
          {
            unsupported_image_type: "이 형식은 보낼 수 없어요 — jpg·png·webp·gif 만 가능해요",
            image_too_large: "이미지가 너무 커요 — 5MB 이하로 줄여주세요",
          }[detail] ?? "이미지 업로드에 실패했어요 — 잠시 후 다시 시도해주세요",
        );
      });
  }, []);

  const onDetachImage = useCallback(() => {
    setAttachedImage((prev) => {
      if (prev) URL.revokeObjectURL(prev.url);
      return null;
    });
  }, []);

  // 전송 — 낙관적 렌더 → 확정 치환, 실패 시 재시도
  const send = useCallback(
    async (pendingEntry?: PendingMessage) => {
      const body = pendingEntry?.body ?? input.trim();
      const item = pendingEntry?.item ?? attachedItem;
      const imageId = pendingEntry?.imageId ?? attachedImage?.imageId ?? null;
      const imageUrl = pendingEntry?.imageUrl ?? attachedImage?.url ?? null;
      if (!body && !item && !imageId) return;
      if (!pendingEntry && attachedImage?.uploading) return; // 업로드 완료 대기
      const client_msg_id = pendingEntry?.client_msg_id ?? newClientMsgId();

      if (!pendingEntry) {
        setInput("");
        setAttachedItem(null);
        setAttachedImage(null);
        setPending((prev) => [
          ...prev,
          { client_msg_id, body, item, imageId, imageUrl, failed: false },
        ]);
        requestAnimationFrame(scrollToBottom);
      } else {
        setPending((prev) =>
          prev.map((x) =>
            x.client_msg_id === client_msg_id ? { ...x, failed: false } : x,
          ),
        );
      }

      try {
        const saved = await chatApi.send({
          to_user_id: otherId,
          body,
          client_msg_id,
          item_id: item?.id,
          image_id: imageId ?? undefined,
        });
        setPending((prev) =>
          prev.filter((x) => x.client_msg_id !== client_msg_id),
        );
        setMessages((prev) =>
          prev.some((m) => m.id === saved.id) ? prev : [...prev, saved],
        );
        if (stickBottom.current) requestAnimationFrame(scrollToBottom);
      } catch (e) {
        setPending((prev) =>
          prev.map((x) =>
            x.client_msg_id === client_msg_id ? { ...x, failed: true } : x,
          ),
        );
        if (e instanceof Error && e.message === "not_friends") {
          setError("친구 관계가 아니에요 — 다시 친구를 맺으면 보낼 수 있어요");
        }
      }
    },
    [input, attachedItem, attachedImage, otherId, scrollToBottom],
  );

  const skinProps = {
    peerName,
    online,
    typing,
    myId,
    messages,
    pending,
    otherRead,
    hasMore,
    error,
    input,
    attachedItem,
    attachedImage,
    listRef,
    onScroll,
    onInputChange: (value: string) => {
      setInput(value);
      sendTyping(otherId); // 클라 3초 스로틀 내장
    },
    onSend: () => send(),
    onRetry: (entry: PendingMessage) => send(entry),
    onPickKaomoji: (k: string) => setInput((v) => v + k),
    onAttachItem: setAttachedItem,
    onDetachItem: () => setAttachedItem(null),
    onAttachImageFile,
    onDetachImage,
  };

  return skinProps;
}
