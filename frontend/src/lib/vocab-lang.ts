/** 어휘망 언어 선택 — 어휘망 화면 상단 언어 칩 (docs/specs/word-insight.md
 *  §어휘망 언어별 분리). 학습 데이터가 있는 언어만 칩으로 노출되며, 선택은
 *  기기별 localStorage 로 유지된다 (game-lang.ts 와 동일한 패턴, 화면이
 *  달라 키만 분리). */

export type VocabLang = "ko" | "en" | "ja";

const STORAGE_KEY = "vocab.lang";

export function isVocabLang(v: string | null | undefined): v is VocabLang {
  return v === "ko" || v === "en" || v === "ja";
}

export function readVocabLang(): VocabLang | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem(STORAGE_KEY);
  return isVocabLang(v) ? v : null;
}

export function writeVocabLang(lang: VocabLang): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, lang);
}
