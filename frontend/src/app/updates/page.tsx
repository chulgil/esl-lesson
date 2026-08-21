"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Brick } from "@/components/brick/Brick";
import {
  CHANGELOG,
  CHANGELOG_SEEN_KEY,
  LATEST_CHANGELOG_DATE,
} from "@/lib/changelog";

/** 업데이트 소식 — 버전(배포일)별로 무엇이 좋아졌는지 보여주는 신뢰 화면
 *  (2026-08-21 요청: 계속 업데이트되는 모습을 보여 고객 신뢰를 높인다).
 *  진입점: 새 버전 배너(BuildRefreshWatcher, ?refresh=1) · 홈 새소식 배너. */
export default function UpdatesPage() {
  return (
    <Suspense fallback={null}>
      <UpdatesInner />
    </Suspense>
  );
}

function UpdatesInner() {
  const fromStale = useSearchParams().get("refresh") === "1";
  // null=확인 중, true=구버전(업데이트 버튼), false=이미 최신(확인 문구)
  const [stale, setStale] = useState<boolean | null>(null);

  // 열람 즉시 "봤음" 기록 — 홈 새소식 배너가 다시 조르지 않는다
  useEffect(() => {
    try {
      localStorage.setItem(CHANGELOG_SEEN_KEY, LATEST_CHANGELOG_DATE);
    } catch {
      // 저장 실패는 무해 — 배너가 한 번 더 보일 뿐
    }
  }, []);

  // CTA 는 실제로 구버전일 때만 — reload 후에도 ?refresh=1 이 남아 버튼이
  // 계속 노출되던 혼란 픽스 (2026-08-21 보고). 번들 SHA 실측으로 판정한다
  useEffect(() => {
    if (!fromStale) return;
    const mine = process.env.NEXT_PUBLIC_BUILD_SHA ?? "dev";
    if (mine === "dev") {
      setStale(false);
      return;
    }
    fetch("/build-version", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setStale(Boolean(data?.sha && data.sha !== mine)))
      .catch(() => setStale(false));
  }, [fromStale]);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <div className="mx-auto w-full max-w-2xl">
        <header className="mb-2 text-center">
          <h1 className="font-hand text-3xl font-bold">
            <span className="hl">업데이트 소식</span>
          </h1>
          <p className="mt-2 text-sm opacity-70">
            레슨아자는 여러분의 피드백으로 매일 좋아지고 있어요.
          </p>
        </header>

        {/* 새 버전 배너에서 온 경우 — 실제 구버전일 때만 업데이트 버튼,
            이미 최신이면 완료 확인 문구 (버튼이 반복 노출되던 혼란 픽스) */}
        {fromStale && stale === true && (
          <div className="mx-auto mt-4 flex max-w-md flex-col items-center gap-2 rounded-lg border-2 border-brick-blue/50 bg-white p-4 text-center">
            <p className="text-sm font-bold">
              새 버전이 준비됐어요 — 아래 내용을 확인하고 업데이트하세요
            </p>
            <Brick
              color="green"
              onClick={() => window.location.replace("/updates")}
            >
              확인 — 최신 버전으로 업데이트
            </Brick>
          </div>
        )}
        {fromStale && stale === false && (
          <p className="mx-auto mt-4 max-w-md rounded-lg border-2 border-brick-green/50 bg-brick-green/10 p-3 text-center text-sm font-bold text-brick-green">
            [v] 최신 버전을 사용 중이에요
          </p>
        )}

        <div className="mt-6 flex flex-col gap-5">
          {CHANGELOG.map((entry) => (
            <section
              key={entry.date}
              className="rounded-lg border-2 border-ink/10 bg-white p-5 text-left"
            >
              <div className="flex flex-wrap items-baseline gap-2">
                <h2 className="font-hand text-2xl font-bold">{entry.title}</h2>
                <span className="text-xs opacity-50">{entry.date}</span>
              </div>
              <ul className="mt-3 flex flex-col gap-1.5 text-sm">
                {entry.items.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span
                      className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brick-green"
                      aria-hidden
                    />
                    {item}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        <p className="mt-8 text-center text-sm">
          <Link
            href="/"
            className="font-bold text-brick-blue underline-offset-2 hover:underline"
          >
            홈으로 돌아가기 →
          </Link>
        </p>
      </div>
    </main>
  );
}
