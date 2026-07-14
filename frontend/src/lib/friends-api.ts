/** 친구 API — 관전 진입용 (docs/specs/study-spectate.md) */

export interface FriendEntry {
  user_id: number;
  name: string;
  avatar_url: string | null;
  studying: boolean;
  watch_code: string | null;
}

export interface FriendRequestEntry {
  id: number;
  name: string;
}

export interface FriendsList {
  friends: FriendEntry[];
  incoming: FriendRequestEntry[];
  outgoing: FriendRequestEntry[];
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
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const friendsApi = {
  list: () => request<FriendsList>("/api/friends"),
  request: (email: string) =>
    request<{ id: number }>("/api/friends/requests", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  accept: (requestId: number) =>
    request<{ id: number }>(`/api/friends/requests/${requestId}/accept`, {
      method: "POST",
    }),
  decline: (requestId: number) =>
    request<void>(`/api/friends/requests/${requestId}`, { method: "DELETE" }),
  remove: (userId: number) =>
    request<void>(`/api/friends/${userId}`, { method: "DELETE" }),
};
