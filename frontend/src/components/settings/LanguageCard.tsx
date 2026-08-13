"use client";

import { useEffect, useState } from "react";
import { studyApi } from "@/lib/study-api";

const LANGS = [
  { value: "ko", label: "한국어" },
  { value: "en", label: "영어" },
  { value: "ja", label: "일본어" },
] as const;

type Lang = (typeof LANGS)[number]["value"];

/** 언어·번역 설정 — 주언어(1개) · 학습언어(복수, 주언어 제외) · 채팅 자동번역.
 *  내 주언어 메시지는 학습언어로, 학습언어 메시지는 주언어로 자동 번역된다. */
export function LanguageCard() {
  const [primaryLang, setPrimaryLang] = useState<Lang | null>(null);
  const [learningLangs, setLearningLangs] = useState<Lang[]>([]);
  const [chatTranslate, setChatTranslate] = useState(false);
  const [translateMine, setTranslateMine] = useState(true);
  const [translateTheirs, setTranslateTheirs] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    studyApi
      .getSettings()
      .then((s) => {
        setPrimaryLang(s.primary_lang);
        setLearningLangs(s.learning_langs as Lang[]);
        setChatTranslate(s.chat_translate);
        setTranslateMine(s.translate_mine);
        setTranslateTheirs(s.translate_theirs);
      })
      .catch(() => undefined);
  }, []);

  function flashSaved() {
    setSaved(true);
    setTimeout(() => setSaved(false), 1800);
  }

  async function patch(body: {
    primary_lang?: Lang;
    learning_langs?: Lang[];
    chat_translate?: boolean;
    translate_mine?: boolean;
    translate_theirs?: boolean;
  }) {
    setBusy(true);
    try {
      const s = await studyApi.patchSettings(body);
      setPrimaryLang(s.primary_lang);
      setLearningLangs(s.learning_langs as Lang[]);
      setChatTranslate(s.chat_translate);
      setTranslateMine(s.translate_mine);
      setTranslateTheirs(s.translate_theirs);
      flashSaved();
    } catch {
      // 실패 시 기존 값 유지
    }
    setBusy(false);
  }

  function choosePrimary(lang: Lang) {
    if (lang === primaryLang) return;
    // 주언어와 겹치는 학습언어는 선택할 수 없다 — 자동으로 제외
    patch({
      primary_lang: lang,
      learning_langs: learningLangs.filter((l) => l !== lang),
    });
  }

  function toggleLearning(lang: Lang) {
    const next = learningLangs.includes(lang)
      ? learningLangs.filter((l) => l !== lang)
      : [...learningLangs, lang];
    patch({ learning_langs: next });
  }

  if (primaryLang === null) {
    return (
      <div className="mt-10 h-60 max-w-lg animate-pulse rounded-lg bg-ink/5" />
    );
  }

  return (
    <section className="mt-10 max-w-lg">
      <p className="mb-1 text-sm font-bold">언어·번역</p>
      <p className="mb-3 text-xs opacity-60">
        내 주언어 메시지는 학습언어로, 학습언어 메시지는 주언어로 번역돼요
      </p>

      <p className="mb-1.5 text-xs font-bold opacity-70">주언어</p>
      <div className="mb-4 flex flex-wrap gap-2">
        {LANGS.map((l) => {
          const active = primaryLang === l.value;
          return (
            <button
              key={l.value}
              type="button"
              disabled={busy}
              aria-pressed={active}
              onClick={() => choosePrimary(l.value)}
              className={`min-h-10 rounded-full border-2 px-4 text-sm font-bold transition disabled:opacity-50 ${
                active
                  ? "border-ink bg-ink text-white"
                  : "border-ink/15 bg-white hover:border-ink/40"
              }`}
            >
              {l.label}
            </button>
          );
        })}
      </div>

      <p className="mb-1.5 text-xs font-bold opacity-70">
        학습언어 (복수 선택 가능)
      </p>
      <div className="mb-4 flex flex-wrap gap-2">
        {LANGS.filter((l) => l.value !== primaryLang).map((l) => {
          const active = learningLangs.includes(l.value);
          return (
            <button
              key={l.value}
              type="button"
              disabled={busy}
              aria-pressed={active}
              onClick={() => toggleLearning(l.value)}
              className={`min-h-10 rounded-full border-2 px-4 text-sm font-bold transition disabled:opacity-50 ${
                active
                  ? "border-brick-blue bg-brick-blue/10 text-brick-blue"
                  : "border-ink/15 bg-white hover:border-brick-blue/50"
              }`}
            >
              {l.label}
            </button>
          );
        })}
      </div>

      <label className="flex min-h-11 max-w-fit cursor-pointer items-center gap-2 rounded-md border-2 border-ink/20 bg-white px-4 text-sm font-bold transition hover:border-ink/50">
        <input
          type="checkbox"
          checked={chatTranslate}
          disabled={busy}
          onChange={(e) => patch({ chat_translate: e.target.checked })}
          className="h-4 w-4"
        />
        채팅 자동번역
      </label>

      {/* 번역 범위 — 내 글/상대 글 개별 체크 (2026-08-12 요청, 기본 내 글만) */}
      {chatTranslate && (
        <div className="mt-2 flex flex-wrap gap-2 pl-1">
          <label className="flex min-h-9 cursor-pointer items-center gap-1.5 rounded-md border-2 border-ink/15 bg-white px-3 text-xs font-bold transition hover:border-ink/40">
            <input
              type="checkbox"
              checked={translateMine}
              disabled={busy}
              onChange={(e) => patch({ translate_mine: e.target.checked })}
              className="h-3.5 w-3.5"
            />
            내가 쓴 글 번역
          </label>
          <label className="flex min-h-9 cursor-pointer items-center gap-1.5 rounded-md border-2 border-ink/15 bg-white px-3 text-xs font-bold transition hover:border-ink/40">
            <input
              type="checkbox"
              checked={translateTheirs}
              disabled={busy}
              onChange={(e) => patch({ translate_theirs: e.target.checked })}
              className="h-3.5 w-3.5"
            />
            상대가 쓴 글 번역
          </label>
        </div>
      )}

      {saved && (
        <p className="mt-2 text-xs font-bold text-brick-green">저장했어요</p>
      )}
    </section>
  );
}
