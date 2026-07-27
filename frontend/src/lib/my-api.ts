/** 개인 콘텐츠 API (docs/specs/content-pipeline.md 콘텐츠 가시성) */

import type { ContentSummary, Job, Segment } from "@/lib/admin-api";

export interface MyItem {
  id: number;
  item_type: "word" | "idiom" | "pattern" | "sentence";
  level: number;
  en_text: string;
  ko_text: string;
  hint_thinking: string | null;
  review_status: string;
  context_en: string | null;
  excluded: boolean;
}

export interface MyContentDetail extends ContentSummary {
  url: string | null;
  segments: Segment[];
  jobs: Job[];
  items: MyItem[];
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

export const myApi = {
  list: () =>
    request<{ total: number; items: ContentSummary[] }>("/api/my/contents"),
  get: (id: number) => request<MyContentDetail>(`/api/my/contents/${id}`),
  // 등록은 관리자 전용 — 사용자는 담기/빼기만 (docs/specs/content-governance.md)
  subscribe: (id: number) =>
    request<{ id: number; subscribed: boolean }>(
      `/api/my/contents/${id}/subscribe`,
      { method: "POST" },
    ),
  retry: (id: number) =>
    request<{ id: number }>(`/api/my/contents/${id}/retry`, { method: "POST" }),
  remove: (id: number) =>
    request<void>(`/api/my/contents/${id}`, { method: "DELETE" }),
  exclude: (itemId: number) =>
    request<{ item_id: number }>(`/api/my/items/${itemId}/exclude`, {
      method: "POST",
    }),
  include: (itemId: number) =>
    request<{ item_id: number }>(`/api/my/items/${itemId}/include`, {
      method: "POST",
    }),
};
