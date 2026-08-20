import { NextRequest, NextResponse } from "next/server";
import {
  SESSION_COOKIE,
  isPublicPath,
  loginRedirectPath,
  sessionExpired,
} from "@/lib/auth-gate";

const ADMIN_HOST_PREFIX = "esladmin.";

/**
 * 단일 도메인 통합 (2026-07-12): 백오피스는 /admin 경로 하나로 접근한다.
 * - esl.lessonaza.app/admin : 관리자만 (역할 검증은 AdminLayout + 백엔드 API)
 * - 기존 esladmin.* 호스트는 하위호환으로 / → /admin 유도만 유지
 * 여기서는 /admin 접근을 막지 않는다 — 비관리자는 AdminLayout 이 안내한다.
 *
 * 세션 게이트 (2026-08-20): 보호 경로는 진입 전에 세션 쿠키(exp)를 확인해
 * 없거나 만료면 /login?next= 으로 라우팅한다 — 만료 토큰으로 화면이 열려
 * 모든 위젯이 "not authenticated" 로 깨지던 현상 해소 (docs/specs/auth.md
 * §세션 만료 라우팅). 서명 검증은 백엔드 몫 — 여기는 라우팅 UX 게이트다.
 */
export function middleware(request: NextRequest) {
  const host = request.headers.get("host") ?? "";
  const { pathname, search } = request.nextUrl;

  if (host.startsWith(ADMIN_HOST_PREFIX) && !pathname.startsWith("/admin")) {
    const url = request.nextUrl.clone();
    url.pathname = pathname === "/" ? "/admin" : `/admin${pathname}`;
    return NextResponse.rewrite(url);
  }

  if (!isPublicPath(pathname)) {
    const token = request.cookies.get(SESSION_COOKIE)?.value;
    if (!token || sessionExpired(token)) {
      const url = request.nextUrl.clone();
      const redirect = loginRedirectPath(pathname + search, Boolean(token));
      url.pathname = redirect.split("?")[0];
      url.search = redirect.split("?")[1] ?? "";
      return NextResponse.redirect(url);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|api|ws|favicon.ico|.*\\..*).*)"],
};
