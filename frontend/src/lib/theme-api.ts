/** 테마 몰 API — 카탈로그·지급·회수 (docs/specs/theme-mall.md) */

export type ThemeAccess = "free" | "restricted";

export interface ThemeCatalogItem {
  key: string;
  access: ThemeAccess;
  /** 내 계정 기준 사용 가능 여부 — free 전부 + 지급받은 제한 테마 */
  allowed: boolean;
  /** 해금 업적 제목 — 보상 규칙이 있으면 잠금 배지 문구로 노출 */
  unlock: string | null;
}

/** 업적→테마 보상 규칙 (백오피스 관리) */
export interface ThemeRewardRule {
  id: number;
  achievement_key: string;
  achievement_title: string;
  theme_key: string;
  created_at: string;
}

export interface AdminThemeItem {
  key: string;
  access: ThemeAccess;
  /** 보유자 수 (grant 행 수) */
  grants: number;
}

export interface ThemeGrantItem {
  id: number;
  email: string;
  nickname: string;
  note: string | null;
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
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const themeApi = {
  themes: () => request<{ items: ThemeCatalogItem[] }>("/api/themes"),

  adminThemes: () => request<{ items: AdminThemeItem[] }>("/api/admin/themes"),

  setAccess: (key: string, access: ThemeAccess) =>
    request<{ key: string; access: ThemeAccess }>(`/api/admin/themes/${key}`, {
      method: "PATCH",
      body: JSON.stringify({ access }),
    }),

  grants: (key: string) =>
    request<{ items: ThemeGrantItem[] }>(`/api/admin/themes/${key}/grants`),

  grant: (key: string, body: { email: string; note?: string }) =>
    request<ThemeGrantItem>(`/api/admin/themes/${key}/grants`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  revoke: (id: number) =>
    request<void>(`/api/admin/themes/grants/${id}`, { method: "DELETE" }),

  rewardRules: () =>
    request<{
      items: ThemeRewardRule[];
      achievements: { key: string; title: string }[];
    }>("/api/admin/themes/rewards"),

  createRewardRule: (body: { achievement_key: string; theme_key: string }) =>
    request<ThemeRewardRule>("/api/admin/themes/rewards", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  deleteRewardRule: (id: number) =>
    request<void>(`/api/admin/themes/rewards/${id}`, { method: "DELETE" }),
};
