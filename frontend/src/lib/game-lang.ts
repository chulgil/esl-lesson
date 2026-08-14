/** 게임 언어 선택 — 게임 허브 상단 언어 칩 (docs/specs/chat-language-rooms.md
 *  §게임 언어 분리). 기본값은 학습언어 중 첫 번째, 기기별 localStorage 로
 *  유지되어 솔로 시작·방 생성이 이 값을 시작 파라미터로 넘긴다. */

export type GameLang = "ko" | "en" | "ja";

const STORAGE_KEY = "game.lang";

export function isGameLang(v: string | null | undefined): v is GameLang {
  return v === "ko" || v === "en" || v === "ja";
}

export function readGameLang(): GameLang | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem(STORAGE_KEY);
  return isGameLang(v) ? v : null;
}

export function writeGameLang(lang: GameLang): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, lang);
}
