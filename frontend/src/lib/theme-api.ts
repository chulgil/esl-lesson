/** 테마 몰 API — 카탈로그·지급·회수 (docs/specs/theme-mall.md) */

export type ThemeAccess = "free" | "restricted";

export interface ThemeCatalogItem {
  key: string;
  access: ThemeAccess;
  /** 내 계정 기준 사용 가능 여부 — free 전부 + 지급받은 제한 테마 */
  allowed: boolean;
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

  grants: (key: string) =>
    request<{ items: ThemeGrantItem[] }>(`/api/admin/themes/${key}/grants`),

  grant: (key: string, body: { email: string; note?: string }) =>
    request<ThemeGrantItem>(`/api/admin/themes/${key}/grants`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  revoke: (id: number) =>
    request<void>(`/api/admin/themes/grants/${id}`, { method: "DELETE" }),
};
