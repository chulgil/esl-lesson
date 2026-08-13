/** 친구 1:1 채팅 API — 전송은 REST 멱등 POST, 수신은 WS (docs/specs/chat.md) */

/** 자동 번역 결과 — 상대 언어 자동 감지 후 내 주언어/학습언어로 번역 (i18n) */
export interface Translation {
  lang: "ko" | "en" | "ja";
  text: string;
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

export interface ChatConversation {
  conversation_id: number;
  user_id: number;
  name: string;
  online: boolean;
  last_message: string | null;
  last_message_at: string | null;
  unread: number;
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
}

/** 대화방 공지 — 대화당 1개, 두 참가자 모두 수정 가능 (docs/specs/chat-notice.md) */
export interface ChatNotice {
  text: string | null;
  updated_at?: string | null;
  updated_by_name?: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const chatApi = {
  deleteMessage: (id: number) =>
    request<void>(`/api/chat/messages/${id}`, { method: "DELETE" }),

  conversations: () =>
    request<{ items: ChatConversation[] }>("/api/chat/conversations"),
  unreadTotal: () => request<{ total: number }>("/api/chat/unread-total"),
  messages: (userId: number, before?: number) =>
    request<{
      items: ChatMessage[];
      reads: Record<string, number>;
      online: boolean;
      peer: { user_id: number; name: string } | null;
      /** 이 대화에 자동번역이 켜져 있는가 — WS 수신 메시지 번역 조회 여부 판단 */
      translate: boolean;
      translate_mine: boolean;
      translate_theirs: boolean;
    }>(`/api/chat/with/${userId}/messages${before ? `?before=${before}` : ""}`),
  /** WS 로 도착한 메시지의 번역 — 비동기 완료 후 1회 조회 (i18n) */
  translation: (id: number) =>
    request<{ translation: Translation | null }>(
      `/api/chat/messages/${id}/translation`,
    ),
  send: (body: {
    to_user_id: number;
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
  markRead: (userId: number) =>
    request<{ ok: boolean }>(`/api/chat/with/${userId}/read`, {
      method: "POST",
    }),
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

  // --- 대화방 공지 (docs/specs/chat-notice.md) ---
  notice: (otherId: number) =>
    request<ChatNotice>(`/api/chat/with/${otherId}/notice`),
  setNotice: (otherId: number, text: string) =>
    request<ChatNotice>(`/api/chat/with/${otherId}/notice`, {
      method: "PUT",
      body: JSON.stringify({ text }),
    }),
  clearNotice: (otherId: number) =>
    request<void>(`/api/chat/with/${otherId}/notice`, { method: "DELETE" }),
};

/** 멱등키 — 재시도해도 서버에 한 건만 저장된다 */
export function newClientMsgId(): string {
  return `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
