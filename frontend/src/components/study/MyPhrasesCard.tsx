"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { studyApi } from "@/lib/study-api";

/** 내가 쓰는 말 덱 — 채팅 발화가 학습 재료가 된다 (docs/specs/my-phrases.md).
 *
 *  남의 문장이 아니라 **내 말투**가 학습언어로 어떻게 되는지 반복 노출 —
 *  복습 큐와 문장 게임(타자·어순·받아쓰기)에 자동 출제된다. 조회가 곧
 *  동기화(lazy sync)라 카드를 열 때마다 최근 채팅이 반영된다. */
export function MyPhrasesCard() {
  const [data, setData] = useState<{
    content_id: number;
    total: number;
    added_now: number;
    recent: { en: string; ko: string }[];
  } | null>(null);

  useEffect(() => {
    const load = () =>
      studyApi
        .myPhrases()
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
  }, []);

  if (data === null) return null;

  return (
    <section className="mt-5 max-w-4xl rounded-xl border-2 border-brick-blue/40 bg-white p-5 shadow-sm">
      <h2 className="font-hand text-2xl font-bold">내가 쓰는 말</h2>
      <p className="mt-1 text-xs opacity-60">
        채팅에서 두 번 이상 쓴 말이 학습 문장이 돼요 — 복습과 타자·어순·받아쓰기
        게임에 자동으로 나와요 (이미 익힌 문장은 게임에서 빠져요)
        {data.added_now > 0 && (
          <b className="ml-1 text-brick-green">+{data.added_now} 새로 수집</b>
        )}
      </p>

      {data.total === 0 ? (
        <p className="mt-3 text-sm opacity-70">
          아직 모인 문장이 없어요 — 설정에서 <b>채팅 자동번역</b>을 켜고 친구와
          대화하면 내 말이 여기에 쌓여요.{" "}
          <Link href="/settings" className="underline underline-offset-2">
            설정 열기
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
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Link
              href={`/study/session?content=${data.content_id}`}
              className="inline-flex min-h-10 items-center rounded-md border-2 border-brick-blue/60 bg-white px-3 text-sm font-bold text-brick-blue transition hover:-translate-y-0.5 hover:border-brick-blue"
            >
              내 말투로 학습 ({data.total}문장)
            </Link>
            {/* 편집 — 빼고 싶은 문장 관리 (2026-08-12 요청) */}
            <Link
              href="/study/phrases"
              className="inline-flex min-h-10 items-center rounded-md border-2 border-ink/20 bg-white px-3 text-sm font-bold transition hover:border-ink/50"
            >
              편집
            </Link>
            <span className="text-xs opacity-50">
              게임에도 자동 출제 — 어제 내가 한 말이 문제로 나와요
            </span>
          </div>
        </>
      )}
    </section>
  );
}
