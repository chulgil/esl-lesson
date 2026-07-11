/** same-origin API 헬퍼 — /api 는 traefik(운영)/rewrite(개발)가 백엔드로 라우팅 */

export interface Me {
  id: number;
  email: string;
  name: string;
  avatar_url: string | null;
  role: "admin" | "learner";
}

export async function fetchMe(): Promise<Me | null> {
  try {
    const res = await fetch("/api/me", { credentials: "same-origin" });
    if (!res.ok) return null;
    return (await res.json()) as Me;
  } catch {
    return null;
  }
}

export function loginUrl(next: string = "/"): string {
  return `/api/auth/login?next=${encodeURIComponent(next)}`;
}
