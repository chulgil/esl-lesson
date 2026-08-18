"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SubscribeButton } from "@/components/content/SubscribeButton";
import { studyApi, type MyPhrasesSummary } from "@/lib/study-api";

const LANG_LABELS: Record<string, string> = {
  ko: "한국어",
  en: "영어",
  ja: "일본어",
};

/** 내가 쓰는 말 덱 — 채팅 발화가 학습 재료가 된다 (docs/specs/my-phrases.md).
 *
 *  남의 문장이 아니라 **내 말투**가 학습언어로 어떻게 되는지 반복 노출 —
 *  복습 큐와 문장 게임(타자·어순·받아쓰기)에 자동 출제된다. 조회가 곧
 *  동기화(lazy sync)라 카드를 열 때마다 최근 채팅이 반영된다.
 *  학습언어가 복수면 언어 탭으로 덱을 나눠 보여준다 (2026-08-14 개정). */
export function MyPhrasesCard() {
  const [learningLangs, setLearningLangs] = useState<string[] | null>(null);
  const [lang, setLang] = useState<string | null>(null);
  const [data, setData] = useState<MyPhrasesSummary | null>(null);
  // 사용자가 탭을 직접 고르기 전까지만 자동 폴백 허용 (아래 useEffect)
  const [userPicked, setUserPicked] = useState(false);

  useEffect(() => {
    studyApi
      .getSettings()
      .then((s) => {
        setLearningLangs(s.learning_langs);
        setLang((prev) => prev ?? s.learning_langs[0] ?? "en");
      })
      .catch(() => setLearningLangs([]));
  }, []);

  useEffect(() => {
    if (!lang) return;
    const load = () =>
      studyApi
        .myPhrases(lang)
        .then(setData)
        .catch(() => setData(null));
    load();
    // 편집(빼기) 후 뒤로가기 — 모바일 bfcache 는 리마운트가 없어 stale 목록이
    // 남는다 (2026-08-12 "반영 안 됨" 보고). 화면 복귀 시 재조회
    window.addEventListener("pageshow", load);
    window.addEventListener("focus", load);
    return () => {
      window.removeEventListener("pageshow", load);
      window.removeEventListener("focus", load);
    };
  }, [lang]);

  // 기본 탭 폴백 — 첫 학습언어 덱이 비어 있고 (일반) 수집분이 있으면 (일반)으로.
  // 언어 방 도입(2026-08-14) 이전 사용자는 수집분 전체가 (일반) 덱에 있어,
  // 빈 언어 탭이 기본이면 학습 버튼이 첫 화면에 안 보인다 (2026-08-18 보고
  // "덱 학습을 넣을 수 없다" — 실제로는 (일반) 탭 뒤에 숨어 있었다)
  useEffect(() => {
    if (userPicked || data === null || lang === "legacy") return;
    if (data.total === 0 && data.legacy_total > 0) setLang("legacy");
  }, [data, lang, userPicked]);

  if (data === null || lang === null) return null;

  // (일반) 칩 — 개편 전 수집분이 있을 때만 노출 (docs/specs/my-phrases.md 덱 그룹화)
  const showLegacyTab = data.legacy_total > 0;
  const tabs = [...(learningLangs ?? []), ...(showLegacyTab ? ["legacy"] : [])];
  const isLegacy = lang === "legacy";

  return (
    <section className="mt-5 max-w-4xl rounded-xl border-2 border-brick-blue/40 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-hand text-2xl font-bold">내가 쓰는 말</h2>
        {/* 언어 탭이 2개 이상이거나 (일반) 덱이 있을 때만 탭 노출 (2026-08-14) */}
        {tabs.length > 1 && (
          <div className="flex flex-wrap gap-1.5">
            {tabs.map((l) => (
              <button
                key={l}
                type="button"
                aria-pressed={lang === l}
                onClick={() => {
                  setUserPicked(true);
                  setLang(l);
                }}
                className={`min-h-9 rounded-full border-2 px-3 text-xs font-bold transition ${
                  lang === l
                    ? "border-brick-blue bg-brick-blue/10 text-brick-blue"
                    : "border-ink/15 bg-white hover:border-brick-blue/50"
                }`}
              >
                {l === "legacy" ? "(일반)" : (LANG_LABELS[l] ?? l)}
              </button>
            ))}
          </div>
        )}
      </div>
      {isLegacy ? (
        <p className="mt-1 text-xs opacity-60">
          기존 채팅에서 모인 {data.total}문장 · 새 문장은 학습 방에서 모여요
        </p>
      ) : (
        <p className="mt-1 text-xs opacity-60">
          채팅에서 두 번 이상 쓴 말이 학습 문장이 돼요 — 복습과
          타자·어순·받아쓰기 게임에 자동으로 나와요 (이미 익힌 문장은 게임에서
          빠져요)
          {data.added_now > 0 && (
            <b className="ml-1 text-brick-green">+{data.added_now} 새로 수집</b>
          )}
        </p>
      )}

      {data.total === 0 ? (
        <p className="mt-3 text-sm opacity-70">
          아직 모인 문장이 없어요 — 학습 방을 만들어 채팅으로 모아보세요.{" "}
          <Link href="/chat" className="underline underline-offset-2">
            채팅 열기
          </Link>
        </p>
      ) : (
        <>
          <ul className="mt-3 flex flex-col gap-1.5">
            {data.recent.map((p) => (
              <li
                key={p.en}
                className="rounded-md border-2 border-ink/10 px-3 py-1.5 text-sm"
              >
                <b>{p.en}</b>
                <span className="ml-2 text-xs opacity-60">{p.ko}</span>
              </li>
            ))}
          </ul>
          {!isLegacy && (
            <p className="mt-2 text-xs font-bold opacity-60">
              활성 {data.active}/100 · 졸업 {data.graduated}
            </p>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {/* 문서함에서 뺀 덱 — 학습 버튼(404) 대신 담기 안내 (2026-08-18) */}
            {!data.subscribed && data.content_id !== null ? (
              <span className="inline-flex flex-wrap items-center gap-2">
                <SubscribeButton
                  contentId={data.content_id}
                  subscribed={false}
                  onChange={() =>
                    studyApi
                      .myPhrases(lang)
                      .then(setData)
                      .catch(() => undefined)
                  }
                />
                <span className="text-xs opacity-60">
                  지금은 학습에서 빠져 있어요 — 담으면 복습·게임에 다시 나와요
                </span>
              </span>
            ) : (
              <Link
                href={`/study/session?content=${data.content_id}`}
                className="inline-flex min-h-10 items-center rounded-md border-2 border-brick-blue/60 bg-white px-3 text-sm font-bold text-brick-blue transition hover:-translate-y-0.5 hover:border-brick-blue"
              >
                {isLegacy
                  ? `이 덱으로 학습 (${data.active}문장)`
                  : `내 말투로 학습 (${data.active}문장)`}
              </Link>
            )}
            {/* 편집 — 빼고 싶은 문장 관리 (2026-08-12 요청) */}
            <Link
              href={`/study/phrases?lang=${lang}`}
              className="inline-flex min-h-10 items-center rounded-md border-2 border-ink/20 bg-white px-3 text-sm font-bold transition hover:border-ink/50"
            >
              편집
            </Link>
            {!isLegacy && (
              <span className="text-xs opacity-50">
                게임에도 자동 출제 — 어제 내가 한 말이 문제로 나와요
              </span>
            )}
          </div>
        </>
      )}
    </section>
  );
}
