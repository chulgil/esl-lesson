"use client";

import { useEffect, useState } from "react";
import { studyApi } from "@/lib/study-api";
import { type GameLang, readGameLang, writeGameLang } from "@/lib/game-lang";

const LANG_LABELS: Record<GameLang, string> = {
  ko: "한국어",
  en: "영어",
  ja: "일본어",
};

/** 게임 허브 상단 언어 칩 — 학습언어가 2개 이상일 때만 노출.
 *  기본값 = learning_langs[0], 선택은 기기별 localStorage(`game.lang`)로
 *  유지된다 (docs/specs/chat-language-rooms.md §게임 언어 분리). 각 게임
 *  페이지가 이 값을 읽어 솔로 시작·방 생성 파라미터로 넘긴다. */
export function GameLangChips() {
  const [learningLangs, setLearningLangs] = useState<GameLang[] | null>(null);
  const [lang, setLang] = useState<GameLang | null>(null);

  useEffect(() => {
    studyApi
      .getSettings()
      .then((s) => {
        const langs = s.learning_langs.filter(
          (l): l is GameLang => l === "ko" || l === "en" || l === "ja",
        );
        setLearningLangs(langs);
        const saved = readGameLang();
        const initial =
          saved && langs.includes(saved) ? saved : (langs[0] ?? null);
        if (initial) {
          setLang(initial);
          writeGameLang(initial);
        }
      })
      .catch(() => setLearningLangs([]));
  }, []);

  if (!learningLangs || learningLangs.length <= 1 || !lang) return null;

  function choose(l: GameLang) {
    setLang(l);
    writeGameLang(l);
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <span className="text-xs font-bold opacity-60">게임 언어</span>
      {learningLangs.map((l) => (
        <button
          key={l}
          type="button"
          aria-pressed={lang === l}
          onClick={() => choose(l)}
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
