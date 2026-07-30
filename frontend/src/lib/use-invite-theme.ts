"use client";

import { useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { APP_THEMES, type AppTheme } from "@/lib/theme";

const VALID_KEYS: ReadonlySet<string> = new Set(APP_THEMES.map((t) => t.key));

/** 초대 링크(?theme=)의 초대자 테마를 게임 화면 동안만 적용 (study-spectate.md 관전과 동일 패턴).
 *
 *  - data-theme 속성만 오버라이드 — setAppTheme 금지: localStorage 에 저장돼
 *    제한 테마가 게스트 설정으로 굳는 엔타이틀먼트 누수가 생긴다.
 *  - ended=true(게임 종료) 또는 언마운트(페이지 이탈) 시 본인 테마로 복원 — 이중 안전망.
 *  - 반환값: 적용 중인 초대자 테마 (canvas 등 useAppTheme 소비 컴포넌트가 대체 사용).
 */
export function useInviteTheme(ended: boolean): AppTheme | null {
  const raw = useSearchParams().get("theme");
  const theme = raw && VALID_KEYS.has(raw) ? (raw as AppTheme) : null;
  const active = theme !== null && !ended;

  useEffect(() => {
    if (!active || !theme) return;
    const root = document.documentElement;
    const prev = root.getAttribute("data-theme");
    root.setAttribute("data-theme", theme);
    return () => {
      if (prev) root.setAttribute("data-theme", prev);
      else root.removeAttribute("data-theme");
    };
  }, [active, theme]);

  return active ? theme : null;
}
