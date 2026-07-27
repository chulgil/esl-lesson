/** 친구 1:1 채팅 API — 전송은 REST 멱등 POST, 수신은 WS (docs/specs/chat.md) */

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
  client_msg_id: string;
  created_at: string | null;
}

export interface ChatConversation {
  conversation_id: number;
  user_id: number;
  name: string;
  avatar_url: string | null;
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
  conversations: () =>
    request<{ items: ChatConversation[] }>("/api/chat/conversations"),
  unreadTotal: () => request<{ total: number }>("/api/chat/unread-total"),
  messages: (userId: number, before?: number) =>
    request<{
      items: ChatMessage[];
      reads: Record<string, number>;
      online: boolean;
      peer: { user_id: number; name: string; avatar_url: string | null } | null;
    }>(`/api/chat/with/${userId}/messages${before ? `?before=${before}` : ""}`),
  send: (body: {
    to_user_id: number;
    body: string;
    client_msg_id: string;
    item_id?: number;
  }) =>
    request<ChatMessage & { created: boolean }>("/api/chat/messages", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  markRead: (userId: number) =>
    request<{ ok: boolean }>(`/api/chat/with/${userId}/read`, {
      method: "POST",
    }),
  shareableItems: (q: string) =>
    request<{ items: ShareableItem[] }>(
      `/api/chat/shareable-items?q=${encodeURIComponent(q)}`,
    ),
};

/** 멱등키 — 재시도해도 서버에 한 건만 저장된다 */
export function newClientMsgId(): string {
  return `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
