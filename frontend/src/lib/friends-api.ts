/** 친구 API — 관전 진입용 (docs/specs/study-spectate.md) */


import { request } from "@/lib/http";

export interface FriendEntry {
  user_id: number;
  name: string;
  avatar_url: string | null;
  studying: boolean;
  watch_code: string | null;
  online: boolean;
  gaming: boolean;
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
