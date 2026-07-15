/** same-origin API 헬퍼 — /api 는 traefik(운영)/rewrite(개발)가 백엔드로 라우팅 */

export interface Me {
  id: number;
  email: string;
  name: string;
  /** 다른 사용자에게 보이는 유일한 이름 — 구글 이름(name)은 비공개 */
  nickname: string;
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

/** 닉네임 변경 — 2~16자, 성공 시 갱신된 Me 반환 */
export async function updateNickname(nickname: string): Promise<Me> {
  const res = await fetch("/api/me", {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nickname }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `${res.status}`);
  }
  return (await res.json()) as Me;
}

/** 회원탈퇴 — 계정·학습 기록 즉시 파기 (개인정보처리방침 3조) */
export async function deleteMe(): Promise<boolean> {
  const res = await fetch("/api/me", {
    method: "DELETE",
    credentials: "same-origin",
  });
  return res.ok;
}
