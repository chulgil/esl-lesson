import { isPublicPath, loginRedirectPath } from "@/lib/auth-gate";

/** 공용 API 요청 헬퍼 — 도메인별 *-api.ts 가 전부 이걸 쓴다.
 *
 *  401(세션 만료/미로그인)은 화면마다 "not authenticated" 에러로 흩어지지
 *  않고 **게이트웨이 규칙으로 로그인에 라우팅**한다 (docs/specs/auth.md
 *  §세션 만료 라우팅). 공개 경로(랜딩 등)에서는 라우팅하지 않는다 —
 *  비로그인 방문자를 로그인으로 튕기면 랜딩이 죽는다. */

const NEED_LOGIN_MESSAGE = "로그인이 필요해요";
let redirecting = false;

function routeToLogin(): void {
  if (typeof window === "undefined" || redirecting) return;
  const { pathname, search } = window.location;
  if (isPublicPath(pathname)) return;
  redirecting = true;
  window.location.assign(loginRedirectPath(pathname + search, true));
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    ...init,
  });
  if (res.status === 401) {
    routeToLogin();
    throw new Error(NEED_LOGIN_MESSAGE);
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`);
  }
  // 204 No Content — 본문이 없어 json() 이 던진다 (2026-08-12 "빼기 미반영")
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}
