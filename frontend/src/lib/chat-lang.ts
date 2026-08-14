/** 언어 학습 대화방 — 언어 표기 헬퍼 (docs/specs/chat-language-rooms.md).
 *  국기 이모지·말풍선은 위장 계약(chat.md) 위반이라 쓰지 않는다 — ASCII 텍스트 태그만. */

import type { SupportedLang } from "@/lib/chat-api";

export const LANG_LABEL: Record<SupportedLang, string> = {
  ko: "한국어",
  en: "영어",
  ja: "일본어",
};

/** 언어쌍 배지용 1글자 표기 — "한→영" 처럼 조합 */
export const LANG_SHORT: Record<SupportedLang, string> = {
  ko: "한",
  en: "영",
  ja: "일",
};

export const SUPPORTED_LANGS: SupportedLang[] = ["ko", "en", "ja"];

export function langPairLabel(
  source: SupportedLang,
  target: SupportedLang,
): string {
  return `${LANG_SHORT[source]}→${LANG_SHORT[target]}`;
}

/** 입력창 placeholder — 방 언어쌍 반영, 테마 중립 (chat-language-rooms.md §UX).
 *  일반 대화 방(plain)은 언어 안내 없이 기본 문구. */
export function roomInputPlaceholder(
  source: SupportedLang | null,
  target: SupportedLang | null,
  mode: "learn" | "plain" = "learn",
): string {
  if (mode === "plain" || !source || !target) return "한 줄 적기...";
  return `${LANG_LABEL[source]}로 쓰면 ${LANG_LABEL[target]}로 보여요`;
}
