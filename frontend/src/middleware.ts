import { NextRequest, NextResponse } from "next/server";

const ADMIN_HOST_PREFIX = "esladmin.";

/**
 * 호스트 기반 분기 (docs/architecture/overview.md)
 * - esladmin.* : 백오피스 전용 — 루트 접근을 /admin 으로 유도
 * - esl.* (서비스) : /admin 경로 차단
 * 역할(role) 검증은 백엔드 API가 담당한다. 여기는 UX 라우팅만.
 */
export function middleware(request: NextRequest) {
  const host = request.headers.get("host") ?? "";
  const { pathname } = request.nextUrl;
  const isAdminHost = host.startsWith(ADMIN_HOST_PREFIX);

  if (isAdminHost && !pathname.startsWith("/admin")) {
    const url = request.nextUrl.clone();
    url.pathname = pathname === "/" ? "/admin" : `/admin${pathname}`;
    return NextResponse.rewrite(url);
  }

  if (!isAdminHost && pathname.startsWith("/admin") && !isLocalhost(host)) {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

function isLocalhost(host: string): boolean {
  return host.startsWith("localhost") || host.startsWith("127.0.0.1");
}

export const config = {
  matcher: ["/((?!_next|api|ws|favicon.ico|.*\\..*).*)"],
};
