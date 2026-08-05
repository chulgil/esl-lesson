/** 테마 키 단일 정본 (2026-08-05 통합) — 유니온 타입(AppTheme)·유효성 검사
 *  (theme.ts isTheme)·부트 화이트리스트(layout.tsx)가 전부 여기서 파생된다.
 *
 *  배경: 키 목록이 3곳에 흩어져 있어 새 테마마다 한 곳을 빠뜨리면 "새로고침에
 *  테마 풀림"(school 사고) 류가 재발했다. 이제 키 추가는 이 배열 한 줄이다.
 *  배열 순서 = 설정 화면 표시 순서.
 *
 *  "use client" 없음 — 서버 컴포넌트(layout.tsx 부트 스크립트)도 값을 읽는다. */
export const THEME_KEYS = [
  "note",
  "candy",
  "lego",
  "cat",
  "school",
  "academy",
  "ocean",
  "excel",
] as const;

export type AppTheme = (typeof THEME_KEYS)[number];
