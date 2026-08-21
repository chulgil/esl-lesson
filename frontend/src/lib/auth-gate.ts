/** 세션 게이트 공용 규칙 — 미들웨어(내비게이션)와 API 클라이언트(fetch 401)가
 *  같은 판단을 공유한다 (docs/specs/auth.md §세션 만료 라우팅).
 *
 *  여기서의 JWT exp 해석은 **라우팅 UX 용**이다 — 서명 검증·인가는 전적으로
 *  백엔드 몫이고, 이 게이트를 우회해도 API 가 401 로 막는다. */

export const SESSION_COOKIE = "els_session";

/** 비로그인에게도 열린 경로 — 랜딩·로그인·정책·빌드 버전 프로브 */
const PUBLIC_PATHS = [
  "/login",
  "/privacy",
  "/copyright",
  "/build-version",
  // 업데이트 소식 — 신뢰 화면이라 비로그인 열람 허용 (updates-changelog.md)
  "/updates",
];

export function isPublicPath(pathname: string): boolean {
  if (pathname === "/") return true;
  return PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
}

/** JWT payload 의 exp 만 읽어 만료 여부 판단 — 파싱 불가/exp 없음 = 만료 취급 */
export function sessionExpired(token: string): boolean {
  try {
    const payload = token.split(".")[1];
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const exp = (JSON.parse(json) as { exp?: unknown }).exp;
    return typeof exp !== "number" || exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

/** 로그인 후 돌아올 경로를 실은 로그인 URL — reason=expired 는 만료 안내 문구용 */
export function loginRedirectPath(next: string, expired: boolean): string {
  const params = new URLSearchParams({ next });
  if (expired) params.set("reason", "expired");
  return `/login?${params.toString()}`;
}
