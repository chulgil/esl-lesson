"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import {
  studyApi,
  type MyPhraseItem,
  type MyPhrasesItemsResponse,
} from "@/lib/study-api";

const LANG_LABELS: Record<string, string> = {
  ko: "한국어",
  en: "영어",
  ja: "일본어",
};

/** 내가 쓰는 말 편집 — 문장 빼기 (docs/specs/my-phrases.md 편집).
 *  뺀 문장은 제외 원장에 기록되어 재동기화(채팅 재수집)에도 돌아오지 않는다.
 *  언어 탭 + 빈도 배지 + 졸업 문장 접힘 섹션 (2026-08-14 개정). */
export default function MyPhrasesEditPage() {
  return (
    // useSearchParams 는 Suspense 경계 필요 (Next.js — session 페이지와 동일 패턴)
    <Suspense>
      <MyPhrasesEditInner />
    </Suspense>
  );
}

function MyPhrasesEditInner() {
  const params = useSearchParams();
  const [learningLangs, setLearningLangs] = useState<string[] | null>(null);
  const [lang, setLang] = useState<string | null>(null);
  const [res, setRes] = useState<MyPhrasesItemsResponse | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    studyApi
      .getSettings()
      .then((s) => {
        setLearningLangs(s.learning_langs);
        const fromQuery = params.get("lang");
        setLang((prev) => prev ?? (fromQuery || s.learning_langs[0] || "en"));
      })
      .catch(() => setLearningLangs([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!lang) return;
    const load = () =>
      studyApi
        .myPhrasesItems(lang)
        .then(setRes)
        .catch(() => setError("목록을 불러오지 못했어요 — 새로고침해 주세요"));
    load();
    // bfcache 복귀 대응 — 다른 화면을 다녀와도 최신 목록 (2026-08-12)
    window.addEventListener("pageshow", load);
    return () => window.removeEventListener("pageshow", load);
  }, [lang]);

  async function remove(itemId: number) {
    setBusy(itemId);
    setError(null);
    try {
      await studyApi.removeMyPhrase(itemId);
      setRes((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.filter((p) => p.id !== itemId),
              graduated_items: prev.graduated_items.filter(
                (p) => p.id !== itemId,
              ),
            }
          : prev,
      );
    } catch {
      setError("빼기에 실패했어요 — 잠시 후 다시 시도해 주세요");
    }
    setBusy(null);
  }

  async function refresh() {
    if (!lang) return;
    setRefreshing(true);
    setError(null);
    try {
      await studyApi.refreshMyPhrases(lang);
      const next = await studyApi.myPhrasesItems(lang);
      setRes(next);
    } catch {
      setError("새로고침에 실패했어요 — 잠시 후 다시 시도해 주세요");
    }
    setRefreshing(false);
  }

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-8 sm:px-10">
      <h1 className="font-hand text-3xl font-bold">
        <span className="hl">내가 쓰는 말 편집</span>
      </h1>
      <p className="mt-2 max-w-lg text-xs opacity-60">
        학습하고 싶지 않은 문장은 빼세요 — 뺀 문장은 복습·게임에서 사라지고,
        같은 말을 다시 채팅해도 다시 수집되지 않아요.
      </p>

      {learningLangs && learningLangs.length > 1 && lang && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {learningLangs.map((l) => (
            <button
              key={l}
              type="button"
              aria-pressed={lang === l}
              onClick={() => setLang(l)}
              className={`min-h-9 rounded-full border-2 px-3 text-xs font-bold transition ${
                lang === l
                  ? "border-brick-blue bg-brick-blue/10 text-brick-blue"
                  : "border-ink/15 bg-white hover:border-brick-blue/50"
              }`}
            >
              {LANG_LABELS[l] ?? l}
            </button>
          ))}
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          href="/study"
          className="inline-flex min-h-10 items-center rounded-md border-2 border-ink/20 bg-white px-3 text-sm font-bold transition hover:border-ink/50"
        >
          ← 학습으로
        </Link>
        {/* 품질 새로고침 — 번역 엔진 개선분을 기존 문장에 적용 (진행도 유지) */}
        <button
          type="button"
          disabled={refreshing || !lang}
          onClick={refresh}
          className="inline-flex min-h-10 items-center rounded-md border-2 border-brick-blue/50 bg-white px-3 text-sm font-bold text-brick-blue transition hover:border-brick-blue disabled:opacity-50"
        >
          {refreshing ? "새로고침 중... (수십 초)" : "번역 품질 새로고침"}
        </button>
      </div>

      {error && <p className="mt-4 text-sm text-brick-red">{error}</p>}

      {res !== null && res.items.length === 0 && res.graduated === 0 && (
        <p className="mt-6 text-sm opacity-70">
          모인 문장이 없어요 — 학습 방에서 채팅하면 이 언어로 쌓여요.
        </p>
      )}

      {res !== null && res.items.length > 0 && (
        <ul className="mt-5 flex max-w-2xl flex-col gap-2">
          {res.items.map((p) => (
            <PhraseRow
              key={p.id}
              item={p}
              busy={busy === p.id}
              disabled={busy !== null}
              onRemove={() => remove(p.id)}
            />
          ))}
        </ul>
      )}

      {res !== null && res.graduated > 0 && (
        <details className="mt-5 max-w-2xl">
          <summary className="min-h-10 cursor-pointer text-sm font-bold opacity-70">
            졸업 {res.graduated}문장 — 장기 기억으로 굳어서 목록에서 숨긴 문장
          </summary>
          <ul className="mt-2 flex flex-col gap-2">
            {res.graduated_items.map((p) => (
              <PhraseRow
                key={p.id}
                item={p}
                busy={busy === p.id}
                disabled={busy !== null}
                onRemove={() => remove(p.id)}
                graduated
              />
            ))}
          </ul>
        </details>
      )}
    </main>
  );
}

function PhraseRow({
  item,
  busy,
  disabled,
  onRemove,
  graduated,
}: {
  item: MyPhraseItem;
  busy: boolean;
  disabled: boolean;
  onRemove: () => void;
  graduated?: boolean;
}) {
  return (
    <li
      className={`flex items-center justify-between gap-3 rounded-md border-2 px-3 py-2 ${
        graduated
          ? "border-ink/10 bg-ink/[0.02] opacity-80"
          : "border-ink/10 bg-white"
      }`}
    >
      <span className="min-w-0">
        <span className="flex items-center gap-2">
          <b className="truncate">{item.en_text}</b>
          {item.freq != null && (
            <span className="shrink-0 rounded-full bg-ink/5 px-2 py-0.5 text-[10px] font-bold opacity-60">
              {item.freq}회
            </span>
          )}
        </span>
        <span className="block truncate text-xs opacity-60">
          {item.ko_text}
        </span>
      </span>
      <button
        type="button"
        disabled={disabled}
        onClick={onRemove}
        className="min-h-11 shrink-0 rounded-full border-2 border-brick-red/40 bg-white px-3 text-xs font-bold text-brick-red transition hover:border-brick-red disabled:opacity-50"
      >
        {busy ? "빼는 중..." : "빼기"}
      </button>
    </li>
  );
}
