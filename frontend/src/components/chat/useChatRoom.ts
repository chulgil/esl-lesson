"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { PendingMessage } from "@/components/chat/skins/types";
import { fetchMe } from "@/lib/api";
import {
  prepareImageForUpload,
  UnsupportedImageError,
} from "@/lib/image-utils";
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
  // 위로 스크롤 페이징 in-flight 가드 — 스크롤 이벤트 연타로 같은 페이지가
  // 병렬 fetch 돼 수십 개씩 중복 프리펜드되던 버그 (2026-07-31 보고)
  const loadingOlder = useRef(false);

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

  // 방 진입·위젯 재열림 시 항상 최신(최하단)부터 보여야 한다 (2026-07-28 보고).
  // 초기 fetch 후 1회 스크롤만으로는 (a) 캐시 복원 렌더 (b) 이미지 로드로
  // 높이가 늦게 자라는 경우 하단이 풀린다 — rAF + 지연 재고정 2회로 보강.
  useEffect(() => {
    requestAnimationFrame(scrollToBottom);
    const t1 = setTimeout(scrollToBottom, 300);
    const t2 = setTimeout(scrollToBottom, 900);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [otherId, scrollToBottom]);

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

  // 재동기화 — WS 끊김·백그라운드 동안 놓친 메시지를 최신 페이지와 병합.
  // id 오름차순 유지(서버 PK 단조 증가), 이미 아는 메시지는 그대로 둔다.
  const resync = useCallback(() => {
    chatApi
      .messages(otherId)
      .then((res) => {
        setMessages((prev) => {
          const known = new Set(prev.map((m) => m.id));
          const fresh = res.items.filter((m) => !known.has(m.id));
          if (fresh.length === 0) return prev;
          // 최신 페이지가 기존과 전혀 안 겹치면(50개 초과 유실) 이어붙이지 않고
          // 최신 페이지로 리셋 — 중간 구멍이 영구 미표시되는 문제 방지.
          // 과거분은 위로 스크롤 페이징이 새 oldest 부터 연속으로 채운다 (심층 리뷰)
          const prevMax = prev.length ? prev[prev.length - 1].id : 0;
          const overlaps = res.items.some((m) => known.has(m.id));
          if (prev.length > 0 && !overlaps && fresh[0].id > prevMax) {
            setHasMore(res.items.length >= 50);
            return [...res.items].sort((a, b) => a.id - b.id);
          }
          return [...prev, ...fresh].sort((a, b) => a.id - b.id);
        });
        setOnline(res.online);
        const reads = res.reads[String(otherId)];
        if (reads) setOtherRead(reads);
        markReadAndSignal();
        if (stickBottom.current) requestAnimationFrame(scrollToBottom);
      })
      .catch(() => {});
  }, [otherId, markReadAndSignal, scrollToBottom]);

  // 새 메시지(수신·낙관 렌더) 도착 시 최하단 고정 — WS 핸들러의 rAF 는 React
  // 렌더 전에 돌아 옛 높이로 스크롤되는 경합이 있었다 (2026-07-31 보고:
  // 챗이 와도 안 내려감). 렌더 후 effect 에서 스크롤해야 새 높이가 반영된다
  const lastCount = useRef(0);
  useEffect(() => {
    const count = messages.length + pending.length;
    if (count > lastCount.current && stickBottom.current) {
      requestAnimationFrame(scrollToBottom);
    }
    lastCount.current = count;
  }, [messages, pending, scrollToBottom]);

  // 탭 복귀·창 포커스 시 재동기화 — 백그라운드 스로틀/절전으로 WS 이벤트를
  // 놓친 경우의 안전망 (2026-07-31 보고: 영역 이탈 후 갱신 안 됨)
  useEffect(() => {
    const onBack = () => {
      if (!document.hidden) resync();
    };
    window.addEventListener("focus", onBack);
    document.addEventListener("visibilitychange", onBack);
    return () => {
      window.removeEventListener("focus", onBack);
      document.removeEventListener("visibilitychange", onBack);
    };
  }, [resync]);

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
      } else if (msg.t === "chat.deleted") {
        // 상대(또는 내 다른 탭)가 삭제 — "삭제되었습니다" 로 즉시 치환
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msg.message_id
              ? {
                  ...m,
                  deleted: true,
                  body: "",
                  item_ref: null,
                  image_url: null,
                }
              : m,
          ),
        );
      } else if (msg.t === "chat.resync") {
        // WS 재접속 — 끊김 동안 놓친 메시지 캐치업
        resync();
      }
    });
  }, [otherId, scrollToBottom, markReadAndSignal, resync]);

  // 내 메시지 삭제 — 낙관적 치환 후 서버 확정 (실패 시 재동기화로 복원)
  const onDeleteMessage = useCallback(
    (id: number) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === id
            ? { ...m, deleted: true, body: "", item_ref: null, image_url: null }
            : m,
        ),
      );
      chatApi.deleteMessage(id).catch(() => resync());
    },
    [resync],
  );

  // 위로 무한스크롤 — in-flight 가드 + id 중복 제거 (같은 페이지 이중 프리펜드 방지)
  const loadOlder = useCallback(async () => {
    const oldest = messages[0];
    if (!oldest || !hasMore || loadingOlder.current) return;
    loadingOlder.current = true;
    const el = listRef.current;
    const prevHeight = el?.scrollHeight ?? 0;
    try {
      const res = await chatApi.messages(otherId, oldest.id);
      setMessages((prev) => {
        const known = new Set(prev.map((m) => m.id));
        const older = res.items.filter((m) => !known.has(m.id));
        return older.length ? [...older, ...prev] : prev;
      });
      setHasMore(res.items.length >= 50);
      requestAnimationFrame(() => {
        if (el) el.scrollTop = el.scrollHeight - prevHeight;
      });
    } finally {
      loadingOlder.current = false;
    }
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
            unsupported_image_type:
              "이 형식은 보낼 수 없어요 — jpg·png·webp·gif 만 가능해요",
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
    onDeleteMessage,
    onPickKaomoji: (k: string) => setInput((v) => v + k),
    onAttachItem: setAttachedItem,
    onDetachItem: () => setAttachedItem(null),
    onAttachImageFile,
    onDetachImage,
  };

  return skinProps;
}
