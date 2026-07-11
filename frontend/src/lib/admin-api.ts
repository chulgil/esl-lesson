/** 백오피스 API 클라이언트 (docs/specs/backoffice.md) */

export interface ContentSummary {
  id: number;
  source: "youtube" | "manual";
  title: string;
  status: "pending" | "extracting" | "ready" | "failed";
  youtube_video_id: string | null;
  error_message: string | null;
  created_at: string;
}

export interface Segment {
  id: number;
  seq: number;
  start_ms: number | null;
  en_text: string;
  ko_text: string | null;
}

export interface Job {
  step: string;
  status: string;
  attempt: number;
  error: string | null;
}

export interface Item {
  id: number;
  item_type: "word" | "idiom" | "pattern" | "sentence";
  level: number;
  en_text: string;
  ko_text: string;
  hint_thinking: string | null;
  pattern_template: string | null;
  difficulty_hint: string;
  review_status: "pending" | "approved" | "rejected";
  context_en: string | null;
}

export interface ContentDetail extends ContentSummary {
  url: string | null;
  segments: Segment[];
  jobs: Job[];
  items: Item[];
}

export interface AdminUser {
  id: number;
  email: string;
  name: string;
  role: "admin" | "learner";
  created_at: string;
  last_login_at: string | null;
  total_reviews: number;
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

export const adminApi = {
  dashboard: () =>
    request<{
      pending_items: number;
      failed_contents: number;
      in_progress_contents: number;
      total_contents: number;
    }>("/api/admin/dashboard"),

  listContents: (status?: string) =>
    request<{ total: number; items: ContentSummary[] }>(
      `/api/admin/contents${status ? `?status=${status}` : ""}`,
    ),

  getContent: (id: number) =>
    request<ContentDetail>(`/api/admin/contents/${id}`),

  createContent: (body: {
    source: "youtube" | "manual";
    url?: string;
    title?: string;
    script_en?: string;
    script_ko?: string;
  }) =>
    request<{ id: number }>("/api/admin/contents", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  retryContent: (id: number) =>
    request<{ id: number }>(`/api/admin/contents/${id}/retry`, {
      method: "POST",
    }),

  deleteContent: (id: number) =>
    request<void>(`/api/admin/contents/${id}`, { method: "DELETE" }),

  patchItem: (
    id: number,
    body: Partial<
      Pick<Item, "en_text" | "ko_text" | "hint_thinking" | "review_status">
    >,
  ) =>
    request<{ id: number }>(`/api/admin/items/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  approveAll: (contentId: number) =>
    request<{ approved: number; skipped: number }>(
      `/api/admin/contents/${contentId}/approve-all`,
      { method: "POST" },
    ),

  listUsers: () => request<{ items: AdminUser[] }>("/api/admin/users"),

  patchUser: (id: number, role: "admin" | "learner") =>
    request<{ id: number }>(`/api/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
};
