"use client";

import type { AlignedWord } from "@/lib/study-api";

/** 문장을 단어 span 으로 렌더 — 현재 재생 단어 하이라이트 + 탭하면 그 단어 반복.
 *  words 가 없으면(미정렬) 평문으로 폴백. (docs/specs/word-alignment.md) */
export function TranscriptWords({
  words,
  text,
  nowMs,
  onWordTap,
}: {
  words: AlignedWord[] | null;
  text: string;
  nowMs: number;
  onWordTap: (word: AlignedWord) => void;
}) {
  if (!words || words.length === 0) {
    return <span>{text}</span>;
  }
  return (
    <span>
      {words.map((word, i) => {
        const active = nowMs >= word.s && nowMs < word.e;
        return (
          <span key={i}>
            <button
              type="button"
              onClick={() => onWordTap(word)}
              className={`rounded px-0.5 transition ${
                active ? "bg-brick-yellow/70 font-bold" : "hover:bg-ink/10"
              }`}
            >
              {word.w}
            </button>{" "}
          </span>
        );
      })}
    </span>
  );
}
