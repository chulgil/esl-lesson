import { NextRequest, NextResponse } from "next/server";

const ADMIN_HOST_PREFIX = "esladmin.";

/**
 * 단일 도메인 통합 (2026-07-12): 백오피스는 /admin 경로 하나로 접근한다.
 * - esl.lessonaza.app/admin : 관리자만 (역할 검증은 AdminLayout + 백엔드 API)
 * - 기존 esladmin.* 호스트는 하위호환으로 / → /admin 유도만 유지
 * 여기서는 /admin 접근을 막지 않는다 — 비관리자는 AdminLayout 이 안내한다.
 */
export function middleware(request: NextRequest) {
  const host = request.headers.get("host") ?? "";
  const { pathname } = request.nextUrl;

  if (host.startsWith(ADMIN_HOST_PREFIX) && !pathname.startsWith("/admin")) {
    const url = request.nextUrl.clone();
    url.pathname = pathname === "/" ? "/admin" : `/admin${pathname}`;
    return NextResponse.rewrite(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|api|ws|favicon.ico|.*\\..*).*)"],
};
