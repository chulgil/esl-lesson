"use client";

import type { VocabLang } from "@/lib/vocab-lang";

const LANG_LABELS: Record<VocabLang, string> = {
  ko: "한국어",
  en: "영어",
  ja: "일본어",
};

/** 어휘망 언어 칩 — 학습 데이터가 있는 언어만 노출 (word-insight.md §어휘망
 *  언어별 분리). langs 는 counts > 0 인 언어만 호출부가 걸러서 넘긴다. */
export function VocabLangChips({
  langs,
  lang,
  onChange,
}: {
  langs: VocabLang[];
  lang: VocabLang;
  onChange: (lang: VocabLang) => void;
}) {
  if (langs.length <= 1) return null;

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <span className="text-xs font-bold opacity-60">언어</span>
      {langs.map((l) => (
        <button
          key={l}
          type="button"
          aria-pressed={lang === l}
          onClick={() => onChange(l)}
          className={`min-h-9 rounded-full border-2 px-3 text-xs font-bold transition ${
            lang === l
              ? "border-brick-blue bg-brick-blue/10 text-brick-blue"
              : "border-ink/15 bg-white hover:border-brick-blue/50"
          }`}
        >
          {LANG_LABELS[l]}
        </button>
      ))}
    </div>
  );
}
