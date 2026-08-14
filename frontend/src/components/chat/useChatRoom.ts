"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { PendingMessage, ReplyDraft } from "@/components/chat/skins/types";
import { fetchMe } from "@/lib/api";
import {
  prepareImageForUpload,
  UnsupportedImageError,
} from "@/lib/image-utils";
import {
  chatApi,
  newClientMsgId,
  roomsApi,
  type ChatMessage,
  type ChatRoom,
  type ShareableItem,
} from "@/lib/chat-api";
import {
  dispatchChatEvent,
  isChatPanelVisible,
  onChatEvent,
  sendTyping,
  setActiveChatRoom,
} from "@/lib/chat-signals";

/** 언어 학습 대화방 데이터·동작 훅 — 전체 페이지와 플로팅 위젯이 공유
 *  (docs/specs/chat-language-rooms.md). room 기준(roomId)으로 동작한다 — 같은
 *  상대와도 언어쌍이 다르면 별개 방이라, 필터링은 항상 conversation_id(=room.id)
 *  기준이어야 한다(peer id 기준이면 다른 방 메시지가 섞인다). 표현(스킨)은
 *  반환된 상태·핸들러만 사용한다. */

// 방별 메모리 캐시 — 재진입 시 즉시 복원 (스펙: 클라이언트 캐싱)
const roomMsgCache = new Map<number, ChatMessage[]>();

export interface AttachedImage {
  url: string; // 로컬 미리보기 (objectURL)
  imageId: string | null; // 업로드 완료 후 서버 파일명
  uploading: boolean;
}

export function useChatRoom(roomId: number) {
  const [myId, setMyId] = useState<number | null>(null);
  const [room, setRoom] = useState<ChatRoom | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>(
    () => roomMsgCache.get(roomId) ?? [],
  );
  const [otherRead, setOtherRead] = useState(0);
  const [typing, setTyping] = useState(false);
  const [pending, setPending] = useState<PendingMessage[]>([]);
  const [input, setInput] = useState("");
  const [attachedItem, setAttachedItem] = useState<ShareableItem | null>(null);
  const [attachedImage, setAttachedImage] = useState<AttachedImage | null>(
    null,
  );
  // 답장 대상 (카톡식 인용) — 전송 시 reply_to_id 로 포함 후 해제
  const [replyDraft, setReplyDraft] = useState<ReplyDraft | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const listRef = useRef<HTMLDivElement>(null);
  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stickBottom = useRef(true);
  // 위로 스크롤 페이징 in-flight 가드 — 스크롤 이벤트 연타로 같은 페이지가
  // 병렬 fetch 돼 수십 개씩 중복 프리펜드되던 버그 (2026-07-31 보고)
  const loadingOlder = useRef(false);

  const peerId = room?.peer.id ?? null;
  // WS 이벤트 핸들러가 최신 myId 를 읽도록 ref 로도 보관 (effect 재구독 최소화)
  const myIdRef = useRef<number | null>(null);
  myIdRef.current = myId;

  useEffect(() => {
    if (messages.length > 0) roomMsgCache.set(roomId, messages.slice(-100));
  }, [messages, roomId]);

  // 보고 있는 방 등록 — 전역 토스트·OS 알림 중복 억제 (위젯과 동일 경로).
  // room id 기준이라야 같은 상대의 다른 언어쌍 방과 섞이지 않는다
  useEffect(() => {
    setActiveChatRoom(roomId);
    return () => setActiveChatRoom(null);
  }, [roomId]);

  const scrollToBottom = useCallback(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  // 방 진입·위젯 재열림 시 항상 최신(최하단)부터 보여야 한다 (2026-07-28 보고).
  useEffect(() => {
    requestAnimationFrame(scrollToBottom);
    const t1 = setTimeout(scrollToBottom, 300);
    const t2 = setTimeout(scrollToBottom, 900);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [roomId, scrollToBottom]);

  const markReadAndSignal = useCallback(() => {
    roomsApi
      .markRead(roomId)
      .then(() =>
        dispatchChatEvent({
          t: "chat.read",
          conversation_id: 0,
          user_id: 0, // 내 읽음 — 배지 갱신 트리거용 로컬 신호
          last_read_message_id: 0,
        }),
      )
      .catch(() => {});
  }, [roomId]);

  // WS 로 도착한 상대 메시지의 번역 — 방 번역은 항상 시도된다(설정 무관,
  // chat-language-rooms.md §번역 규칙). 내 글은 send() 응답에 이미 동봉된다
  const fetchTranslation = useCallback((messageId: number) => {
    chatApi
      .translation(messageId)
      .then((res) => {
        if (!res.translation) return;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === messageId ? { ...m, translation: res.translation } : m,
          ),
        );
      })
      .catch(() => {});
  }, []);

  // 초기 로드
  useEffect(() => {
    if (!Number.isFinite(roomId)) return;
    fetchMe().then((me) => me && setMyId(me.id));
    roomsApi
      .messages(roomId)
      .then((res) => {
        setRoom(res.room);
        setMessages(res.items);
        const reads = res.reads[String(res.room.peer.id)];
        if (reads) setOtherRead(reads);
        setHasMore(res.items.length >= 50);
        markReadAndSignal();
        requestAnimationFrame(scrollToBottom);
      })
      .catch((e) => setError(e.message));
  }, [roomId, scrollToBottom, markReadAndSignal]);

  // 재동기화 — WS 끊김·백그라운드 동안 놓친 메시지를 최신 페이지와 병합.
  // id 오름차순 유지(서버 PK 단조 증가), 이미 아는 메시지는 그대로 둔다.
  const resync = useCallback(() => {
    roomsApi
      .messages(roomId)
      .then((res) => {
        setRoom(res.room);
        setMessages((prev) => {
          const known = new Set(prev.map((m) => m.id));
          const byId = new Map(res.items.map((m) => [m.id, m]));
          const fresh = res.items.filter((m) => !known.has(m.id));
          // 아는 메시지도 서버 값으로 치환해야 한다 — 끊김 중 놓친 chat.deleted
          // 반영 + 삭제 API 실패 시 낙관 치환 복원 (재검토). 메시지는 삭제 외
          // 불변이므로 deleted 플래그 변화만 재렌더 트리거로 본다
          const changedKnown = prev.some((m) => {
            const server = byId.get(m.id);
            return (
              server !== undefined &&
              Boolean(server.deleted) !== Boolean(m.deleted)
            );
          });
          if (fresh.length === 0 && !changedKnown) return prev;
          // 최신 페이지가 기존과 전혀 안 겹치면(50개 초과 유실) 이어붙이지 않고
          // 최신 페이지로 리셋 — 중간 구멍이 영구 미표시되는 문제 방지.
          const prevMax = prev.length ? prev[prev.length - 1].id : 0;
          const overlaps = res.items.some((m) => known.has(m.id));
          if (
            prev.length > 0 &&
            !overlaps &&
            fresh.length > 0 &&
            fresh[0].id > prevMax
          ) {
            setHasMore(res.items.length >= 50);
            return [...res.items].sort((a, b) => a.id - b.id);
          }
          return [...prev.map((m) => byId.get(m.id) ?? m), ...fresh].sort(
            (a, b) => a.id - b.id,
          );
        });
        const reads = res.reads[String(res.room.peer.id)];
        if (reads) setOtherRead(reads);
        // 패널을 접어둔(위장) 동안은 읽음 처리 보류 — 배지·알림이 살아야 한다
        // (2026-08-10 보고: 접힌 화면에서 알림이 전부 침묵)
        if (isChatPanelVisible()) markReadAndSignal();
        if (stickBottom.current) requestAnimationFrame(scrollToBottom);
      })
      .catch(() => {});
  }, [roomId, markReadAndSignal, scrollToBottom]);

  // 새 메시지(수신·낙관 렌더) 도착 시 최하단 고정 — WS 핸들러의 rAF 는 React
  // 렌더 전에 돌아 옛 높이로 스크롤되는 경합이 있었다 (2026-07-31 보고)
  const lastCount = useRef(0);
  useEffect(() => {
    const count = messages.length + pending.length;
    if (count > lastCount.current && stickBottom.current) {
      requestAnimationFrame(scrollToBottom);
    }
    lastCount.current = count;
  }, [messages, pending, scrollToBottom]);

  // 탭 복귀·창 포커스 시 재동기화 — 백그라운드 스로틀/절전으로 WS 이벤트를
  // 놓친 경우의 안전망 (2026-07-31 보고)
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

  // WS 이벤트 구독 — conversation_id(=room.id) 기준으로 필터링해야 같은
  // 상대의 다른 언어쌍 방과 메시지가 섞이지 않는다
  useEffect(() => {
    return onChatEvent((msg) => {
      if (msg.t === "chat.message" && msg.conversation_id === roomId) {
        setMessages((prev) =>
          prev.some((m) => m.id === msg.id) ? prev : [...prev, msg],
        );
        setTyping(false);
        // 접힌(위장) 패널에서는 읽음 보류 — 다시 펼치면 chat.resync 가 처리
        if (isChatPanelVisible()) markReadAndSignal();
        if (stickBottom.current) requestAnimationFrame(scrollToBottom);
        // 상대 글만 번역 조회 — 내 글은 send() 응답에 이미 번역이 동봉된다.
        // WS payload 가 이미 번역을 동봉했으면(방 기준 전송) 재조회하지 않는다
        // (chat-language-rooms.md §API — 전송 응답과 동일하게 WS 도 동봉).
        // 공지 시스템 줄(kind)은 번역 대상이 아니다 (docs/specs/chat-notice.md)
        if (
          !msg.kind &&
          msg.sender_id !== myIdRef.current &&
          msg.translation === undefined
        ) {
          fetchTranslation(msg.id);
        }
      } else if (msg.t === "chat.read" && msg.conversation_id === roomId) {
        setOtherRead(msg.last_read_message_id);
      } else if (msg.t === "chat.typing" && msg.from_user_id === peerId) {
        setTyping(true);
        if (typingTimer.current) clearTimeout(typingTimer.current);
        typingTimer.current = setTimeout(() => setTyping(false), 5000);
      } else if (msg.t === "presence" && msg.user_id === peerId) {
        setRoom((prev) =>
          prev ? { ...prev, peer: { ...prev.peer, online: msg.online } } : prev,
        );
      } else if (msg.t === "chat.deleted" && msg.conversation_id === roomId) {
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
                  translation: null,
                }
              : m,
          ),
        );
      } else if (msg.t === "chat.room_closed" && msg.room_id === roomId) {
        // 상대가 나감 — 방이 종료돼 더 이상 전송할 수 없다
        setRoom((prev) => (prev ? { ...prev, status: "closed" } : prev));
      } else if (msg.t === "chat.resync") {
        // WS 재접속 — 끊김 동안 놓친 메시지 캐치업
        resync();
      }
    });
  }, [
    roomId,
    peerId,
    scrollToBottom,
    markReadAndSignal,
    resync,
    fetchTranslation,
  ]);

  // 내 메시지 삭제 — 낙관적 치환 후 서버 확정 (실패 시 재동기화로 복원)
  const onDeleteMessage = useCallback(
    (id: number) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === id
            ? {
                ...m,
                deleted: true,
                body: "",
                item_ref: null,
                image_url: null,
                translation: null,
              }
            : m,
        ),
      );
      chatApi.deleteMessage(id).catch(() => resync());
    },
    [resync],
  );

  // 방 나가기 — origin=match 방에서만 노출(스킨 판단), closed 로 낙관 반영
  const onLeaveRoom = useCallback(() => {
    roomsApi
      .leave(roomId)
      .then(() =>
        setRoom((prev) => (prev ? { ...prev, status: "closed" } : prev)),
      )
      .catch(() => {});
  }, [roomId]);

  // 위로 무한스크롤 — in-flight 가드 + id 중복 제거 (같은 페이지 이중 프리펜드 방지)
  const loadOlder = useCallback(async () => {
    const oldest = messages[0];
    if (!oldest || !hasMore || loadingOlder.current) return;
    loadingOlder.current = true;
    const el = listRef.current;
    const prevHeight = el?.scrollHeight ?? 0;
    try {
      const res = await roomsApi.messages(roomId, oldest.id);
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
  }, [messages, hasMore, roomId]);

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

  // 전송 — 낙관적 렌더 → 확정 치환, 실패 시 재시도. 번역은 응답에 동봉된다
  // (chat-language-rooms.md §API — WS 조회 왕복 불필요)
  const send = useCallback(
    async (pendingEntry?: PendingMessage) => {
      const body = pendingEntry?.body ?? input.trim();
      const item = pendingEntry?.item ?? attachedItem;
      const imageId = pendingEntry?.imageId ?? attachedImage?.imageId ?? null;
      const imageUrl = pendingEntry?.imageUrl ?? attachedImage?.url ?? null;
      const replyToId = pendingEntry?.replyToId ?? replyDraft?.id ?? null;
      const replyPreview =
        pendingEntry?.replyPreview ?? replyDraft?.preview ?? null;
      if (!body && !item && !imageId) return;
      if (!pendingEntry && attachedImage?.uploading) return; // 업로드 완료 대기
      const client_msg_id = pendingEntry?.client_msg_id ?? newClientMsgId();

      if (!pendingEntry) {
        setInput("");
        setAttachedItem(null);
        setAttachedImage(null);
        setReplyDraft(null);
        setPending((prev) => [
          ...prev,
          {
            client_msg_id,
            body,
            item,
            imageId,
            imageUrl,
            failed: false,
            replyToId,
            replyPreview,
          },
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
        const saved = await roomsApi.send({
          room_id: roomId,
          body,
          client_msg_id,
          item_id: item?.id,
          image_id: imageId ?? undefined,
          reply_to_id: replyToId ?? undefined,
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
        const code = e instanceof Error ? e.message : "";
        if (code === "not_friends") {
          setError("친구 관계가 아니에요 — 다시 친구를 맺으면 보낼 수 있어요");
        } else if (code === "room_closed") {
          setError("종료된 방이에요 — 더 이상 보낼 수 없어요");
        }
      }
    },
    [input, attachedItem, attachedImage, replyDraft, roomId, scrollToBottom],
  );

  const skinProps = {
    room,
    peerName: room?.peer.nickname ?? "",
    peerId,
    online: room?.peer.online ?? false,
    sourceLang: room?.source_lang ?? null,
    targetLang: room?.target_lang ?? null,
    origin: room?.origin ?? null,
    status: room?.status ?? null,
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
      if (peerId != null) sendTyping(peerId); // 클라 3초 스로틀 내장
    },
    onSend: () => send(),
    onRetry: (entry: PendingMessage) => send(entry),
    onDeleteMessage,
    onLeaveRoom,
    replyDraft,
    onReplyTo: (msg: ChatMessage) =>
      setReplyDraft({
        id: msg.id,
        senderId: msg.sender_id,
        preview: msg.deleted
          ? "삭제되었습니다"
          : msg.body || (msg.image_url ? "[사진]" : "[단어 카드]"),
      }),
    onCancelReply: () => setReplyDraft(null),
    onPickKaomoji: (k: string) => setInput((v) => v + k),
    onAttachItem: setAttachedItem,
    onDetachItem: () => setAttachedItem(null),
    onAttachImageFile,
    onDetachImage,
  };

  return skinProps;
}
