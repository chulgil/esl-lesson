"use client";

import { useEffect, useState } from "react";
import { studyApi, type WordInsight } from "@/lib/study-api";

/** 단어 인사이트 바텀시트 — 뉘앙스/유사단어/예문 (docs/proposal/word-insight.md P1) */
export function InsightSheet({
  itemId,
  word,
  onClose,
}: {
  itemId: number;
  word: string;
  onClose: () => void;
}) {
  const [insight, setInsight] = useState<WordInsight | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    setInsight(null);
    setError(false);
    studyApi
      .insight(itemId)
      .then((data) => alive && setInsight(data))
      .catch(() => alive && setError(true));
    return () => {
      alive = false;
    };
  }, [itemId]);

  function speak() {
    // 브라우저 내장 TTS — 서버 비용 없음 (P1 결정)
    const utter = new SpeechSynthesisUtterance(word);
    utter.lang = "en-US";
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/30 sm:items-center"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-t-2xl border-2 border-ink/15 bg-paper p-5 shadow-xl sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={`${word} 단어 정보`}
      >
        <div className="mb-1 flex items-center gap-3">
          <h2 className="font-hand text-3xl font-bold">{word}</h2>
          <button
            type="button"
            onClick={speak}
            aria-label="발음 듣기"
            className="flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border-2 border-brick-blue/40 bg-white text-brick-blue transition hover:border-brick-blue"
          >
            <SpeakerIcon />
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="ml-auto flex h-11 w-11 cursor-pointer items-center justify-center rounded-full text-xl opacity-50 hover:opacity-100"
          >
            ×
          </button>
        </div>

        {error && (
          <p className="py-6 text-center text-sm text-brick-red">
            정보를 불러오지 못했어요 — 잠시 후 다시 열어주세요
          </p>
        )}

        {!insight && !error && <Skeleton />}

        {insight && (
          <div className="flex flex-col gap-4 pb-2">
            <p className="text-sm opacity-70">
              {insight.ipa && <span className="mr-2">{insight.ipa}</span>}
              {insight.pos && (
                <span className="rounded bg-ink/10 px-1.5 py-0.5 text-xs">
                  {insight.pos}
                </span>
              )}
            </p>

            {insight.nuance_ko && (
              <Section title="뉘앙스">
                <p>{insight.nuance_ko}</p>
              </Section>
            )}

            {insight.examples && insight.examples.length > 0 && (
              <Section title="예문">
                <ul className="flex flex-col gap-2">
                  {insight.examples.map((ex) => (
                    <li key={ex.en}>
                      <p className="font-medium">{ex.en}</p>
                      <p className="text-sm opacity-60">{ex.ko}</p>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {insight.collocations && insight.collocations.length > 0 && (
              <Section title="자주 붙는 표현">
                <div className="flex flex-wrap gap-2">
                  {insight.collocations.map((c) => (
                    <span
                      key={c}
                      className="rounded-full bg-highlight/50 px-3 py-1 text-sm"
                    >
                      {c}
                    </span>
                  ))}
                </div>
              </Section>
            )}

            {insight.synonyms && insight.synonyms.length > 0 && (
              <Section title="유의어">
                <WordDiffList items={insight.synonyms} />
              </Section>
            )}

            {insight.confusables && insight.confusables.length > 0 && (
              <Section title="헷갈리기 쉬운 단어">
                <WordDiffList items={insight.confusables} accent />
              </Section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <p className="mb-1.5 text-xs font-bold opacity-50">{title}</p>
      {children}
    </section>
  );
}

function WordDiffList({
  items,
  accent = false,
}: {
  items: { word: string; ko: string; diff_ko: string }[];
  accent?: boolean;
}) {
  return (
    <ul className="flex flex-col gap-2">
      {items.map((s) => (
        <li
          key={s.word}
          className={`rounded-md border-2 bg-white p-2.5 ${
            accent ? "border-brick-yellow/50" : "border-ink/10"
          }`}
        >
          <p className="font-bold">
            {s.word} <span className="font-normal opacity-60">{s.ko}</span>
          </p>
          <p className="text-sm opacity-70">{s.diff_ko}</p>
        </li>
      ))}
    </ul>
  );
}

function Skeleton() {
  return (
    <div className="flex animate-pulse flex-col gap-3 py-2">
      {[64, 100, 88, 72].map((w, i) => (
        <div
          key={i}
          className="h-4 rounded bg-ink/10"
          style={{ width: `${w}%` }}
        />
      ))}
      <p className="mt-1 text-center text-xs opacity-40">
        단어 정보를 만들고 있어요 (첫 조회에만 몇 초 걸려요)
      </p>
    </div>
  );
}

function SpeakerIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M11 5 6 9H2v6h4l5 4V5Z" />
      <path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a9 9 0 0 1 0 14" />
    </svg>
  );
}
