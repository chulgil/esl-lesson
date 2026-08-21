/** 친구 1:1 채팅 API — 전송은 REST 멱등 POST, 수신은 WS (docs/specs/chat.md).
 *  2026-08-14: 언어쌍 학습 방(room)으로 확장 — docs/specs/chat-language-rooms.md.
 *  conversations 테이블 확장이 곧 room 이라 room.id === conversation_id. */

import { request } from "@/lib/http";

export type SupportedLang = "ko" | "en" | "ja";

/** 자동 번역 결과 — 상대 언어 자동 감지 후 내 주언어/학습언어로 번역 (i18n) */
export interface Translation {
  lang: SupportedLang;
  text: string;
}

export type RoomOrigin = "friend" | "match";
export type RoomStatus = "active" | "closed";

export interface ChatRoomPeer {
  id: number;
  nickname: string;
  online: boolean;
}

/** 언어쌍 학습 방 — 상대 1명 + 언어쌍(source→target) 단위. 같은 상대와도
 *  언어쌍이 다르면 별개 방이 될 수 있다 (chat-language-rooms.md §데이터 모델) */
export type RoomMode = "learn" | "plain";

export interface ChatRoom {
  id: number;
  peer: ChatRoomPeer;
  source_lang: SupportedLang;
  target_lang: SupportedLang;
  origin: RoomOrigin;
  status: RoomStatus;
  /** learn=번역 표시 방(기본) / plain=일반 대화(번역 없음) */
  mode: RoomMode;
  last_message_at: string | null;
  unread: number;
  /** 목록 미리보기 — 번역문 우선 (서버가 결정) */
  preview: string | null;
}

export interface ChatRoomMessagesResponse {
  room: ChatRoom;
  items: ChatMessage[];
  reads: Record<string, number>;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  sender_id: number;
  body: string;
  item_ref: {
    item_id: number;
    item_type: string;
    en_text: string;
    ko_text: string;
  } | null;
  image_url: string | null;
  /** soft delete — true 면 "삭제되었습니다" 표기 (내용은 서버가 소거) */
  deleted: boolean;
  client_msg_id: string;
  created_at: string | null;
  /** 답장 인용 (2026-07-31) — 미리보기는 서버가 읽기 시점에 해석 (삭제 반영) */
  reply_to_id?: number | null;
  reply_to?: {
    id: number;
    sender_id: number;
    deleted: boolean;
    preview: string;
  } | null;
  /** 자동 번역 — WS 로 갓 도착한 메시지는 비어 있다가 별도 조회로 채워진다 */
  translation?: Translation | null;
  /** 공지 변경 시스템 줄 (docs/specs/chat-notice.md) — null/미정의면 일반 메시지.
   *  notice_set 의 body 는 공지 첫 줄 스냅샷, notice_clear 의 body 는 빈 문자열 */
  kind?: "notice_set" | "notice_clear" | null;
}

export interface ShareableItem {
  id: number;
  item_type: string;
  en_text: string;
  ko_text: string;
}

/** 함께 목표 — 체크리스트 항목 (docs/specs/shared-goals.md) */
export interface GoalItem {
  id: number;
  text: string;
  done: boolean;
  done_by_name: string | null;
  created_by_name: string | null;
}

/** 이번 주(KST 월요일 시작) 복습 수 합산 — target 대비 각자 기여 */
export interface GoalWeekly {
  target: number;
  mine: number;
  theirs: number;
}

export interface GoalsResponse {
  items: GoalItem[];
  weekly: GoalWeekly;
  /** 주간 목표를 명시 설정했는가 — 보드 노출 판정 (2026-08-13 기본 숨김 전환) */
  weekly_configured: boolean;
}

/** 대화방 공지 — 대화당 1개, 두 참가자 모두 수정 가능 (docs/specs/chat-notice.md) */
export interface ChatNotice {
  /** 제목(한 줄, 80자) — 레거시 행(제목 도입 전)만 null 에 text 존재 가능 */
  title: string | null;
  text: string | null;
  updated_at?: string | null;
  updated_by_name?: string | null;
}

export const chatApi = {
  deleteMessage: (id: number) =>
    request<void>(`/api/chat/messages/${id}`, { method: "DELETE" }),

  unreadTotal: () => request<{ total: number }>("/api/chat/unread-total"),
  /** WS 로 도착한 메시지의 번역 — 비동기 완료 후 1회 조회 (i18n) */
  translation: (id: number) =>
    request<{ translation: Translation | null }>(
      `/api/chat/messages/${id}/translation`,
    ),
  /** 외국어 문장의 한글 독음 — [읽기] 토글 지연 로드 (chat-translation §한글 독음) */
  reading: (text: string, lang: SupportedLang) =>
    request<{ reading: string | null }>(
      `/api/chat/reading?text=${encodeURIComponent(text)}&lang=${lang}`,
    ),
  uploadImage: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/chat/uploads", {
      method: "POST",
      credentials: "same-origin",
      body: form,
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      throw new Error(detail?.detail ?? "upload failed");
    }
    return (await res.json()) as { image_id: string };
  },
  shareableItems: (q: string) =>
    request<{ items: ShareableItem[] }>(
      `/api/chat/shareable-items?q=${encodeURIComponent(q)}`,
    ),

  // --- 함께 목표 (docs/specs/shared-goals.md) ---
  goals: (otherId: number) =>
    request<GoalsResponse>(`/api/chat/with/${otherId}/goals`),
  addGoal: (otherId: number, text: string) =>
    request<GoalItem>(`/api/chat/with/${otherId}/goals`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  patchGoal: (id: number, patch: { text?: string; done?: boolean }) =>
    request<GoalItem>(`/api/chat/goals/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  setWeeklyTarget: (otherId: number, targetValue: number) =>
    request<GoalWeekly>(`/api/chat/with/${otherId}/goals/weekly`, {
      method: "PATCH",
      body: JSON.stringify({ target_value: targetValue }),
    }),
  deleteGoal: (id: number) =>
    request<void>(`/api/chat/goals/${id}`, { method: "DELETE" }),
  clearGoalBoard: (otherId: number) =>
    request<void>(`/api/chat/with/${otherId}/goals`, { method: "DELETE" }),

  // --- 대화방 공지 (docs/specs/chat-notice.md) ---
  notice: (otherId: number) =>
    request<ChatNotice>(`/api/chat/with/${otherId}/notice`),
  setNotice: (otherId: number, title: string, text: string) =>
    request<ChatNotice>(`/api/chat/with/${otherId}/notice`, {
      method: "PUT",
      body: JSON.stringify({ title, text }),
    }),
  clearNotice: (otherId: number) =>
    request<void>(`/api/chat/with/${otherId}/notice`, { method: "DELETE" }),
  /** 공지 체크 항목 토글 — 해당 줄만 원자 치환 (chat-notice.md §공지 체크리스트) */
  checkNotice: (otherId: number, lineIndex: number, checked: boolean) =>
    request<ChatNotice>(`/api/chat/with/${otherId}/notice/check`, {
      method: "PATCH",
      body: JSON.stringify({ line_index: lineIndex, checked }),
    }),
};

/** 언어 학습 대화방 API (docs/specs/chat-language-rooms.md §API) */
export const roomsApi = {
  list: () => request<ChatRoom[]>("/api/chat/rooms"),
  create: (
    peerId: number,
    sourceLang: SupportedLang,
    targetLang: SupportedLang,
    mode: RoomMode = "learn",
  ) =>
    request<{ room: ChatRoom; created: boolean }>("/api/chat/rooms", {
      method: "POST",
      body: JSON.stringify({
        peer_id: peerId,
        source_lang: sourceLang,
        target_lang: targetLang,
        mode,
      }),
    }),
  get: (id: number) => request<ChatRoom>(`/api/chat/rooms/${id}`),
  messages: (id: number, before?: number) =>
    request<ChatRoomMessagesResponse>(
      `/api/chat/rooms/${id}/messages${before ? `?before=${before}` : ""}`,
    ),
  markRead: (id: number) =>
    request<{ ok: boolean }>(`/api/chat/rooms/${id}/read`, { method: "POST" }),
  /** 나가기 — 멱등, closed 로 전환 (204) */
  leave: (id: number) =>
    request<void>(`/api/chat/rooms/${id}/leave`, { method: "POST" }),
  send: (body: {
    room_id: number;
    body: string;
    client_msg_id: string;
    item_id?: number;
    image_id?: string;
    reply_to_id?: number;
  }) =>
    request<ChatMessage & { created: boolean }>("/api/chat/messages", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

/** 랜덤 매칭 대기열 (인프로세스, chat-language-rooms.md §랜덤 매칭) */
export const matchApi = {
  join: (
    sourceLang: SupportedLang,
    targetLang: SupportedLang,
    mode: RoomMode = "learn",
  ) =>
    request<{ room: ChatRoom } | { waiting: true }>("/api/chat/match", {
      method: "POST",
      body: JSON.stringify({
        source_lang: sourceLang,
        target_lang: targetLang,
        mode,
      }),
    }),
  status: () => request<{ waiting: boolean }>("/api/chat/match"),
  cancel: () => request<void>("/api/chat/match", { method: "DELETE" }),
};

/** 멱등키 — 재시도해도 서버에 한 건만 저장된다 */
export function newClientMsgId(): string {
  return `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
