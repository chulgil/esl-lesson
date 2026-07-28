/** 알림 센터 API — 친구 요청·수락·게임 초대 알림함 (docs/specs/notifications.md) */

export interface NotificationItem {
  id: number;
  type: string;
  /** 발생 시점 스냅샷 — 타입별 필드가 달라 unknown 으로 두고 사용처에서 좁힌다 */
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
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

export const notificationsApi = {
  list: () =>
    request<{ items: NotificationItem[]; unread: number }>(
      "/api/notifications",
    ),
  markRead: (body: { all?: boolean; ids?: number[] }) =>
    request<{ ok: boolean }>("/api/notifications/read", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
