import { NextResponse } from "next/server";

/** 현재 서버 번들의 빌드 SHA — 오래 열린 탭이 자기 번들과 비교해
 *  구버전이면 새로고침을 안내한다 (BuildRefreshWatcher, 2026-07-31).
 *  /api/* 는 traefik 이 백엔드로 보내므로 Next 자체 경로를 쓴다.
 *  배포마다 값이 바뀌어야 하므로 캐시 금지. */
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json(
    { sha: process.env.NEXT_PUBLIC_BUILD_SHA ?? "dev" },
    { headers: { "Cache-Control": "no-store" } },
  );
}
