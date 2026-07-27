"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "@/components/content/StatusBadge";
import type { ContentSummary } from "@/lib/admin-api";
import { myApi } from "@/lib/my-api";

/** 내 콘텐츠 — 라이브러리에서 담은 것만 모아 보는 화면.
 *  등록은 관리자 전용이다 (docs/specs/content-governance.md). */
export default function MyContentsPage() {
  const [contents, setContents] = useState<ContentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    myApi
      .list()
      .then((res) => setContents(res.items))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-6 flex flex-wrap items-center gap-4">
        <h1 className="font-hand text-3xl font-bold">
          <span className="hl">내 콘텐츠</span>
        </h1>
        <span className="text-xs opacity-60">
          라이브러리에서 담은 학습 재료
        </span>
        <Link
          href="/library"
          className="ml-auto flex min-h-11 items-center rounded-md border-2 border-brick-blue/50 bg-white px-4 text-sm font-bold text-brick-blue transition hover:-translate-y-0.5 hover:border-brick-blue"
        >
          라이브러리에서 담기
        </Link>
      </header>

      {error && <p className="mb-4 text-sm text-brick-red">{error}</p>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {contents.map((c, i) => (
          <Link
            key={c.id}
            href={`/my/${c.id}`}
            className={`rounded-lg border-2 border-ink/10 bg-white p-4 shadow-sm transition hover:-translate-y-1 ${
              i % 2 ? "rotate-[0.4deg]" : "-rotate-[0.4deg]"
            }`}
          >
            <div className="flex items-center gap-2 text-xs">
              <span className="opacity-50">
                {c.source === "youtube" ? "유튜브" : "수기"}
              </span>
              <StatusBadge status={c.status} />
            </div>
            <p className="mt-2 font-bold">{c.title}</p>
            {/* 진행 안내는 실패가 아니므로 빨간 에러 톤을 쓰지 않는다 */}
            {c.status === "failed" && c.error_message ? (
              <p className="mt-1 text-xs text-brick-red">{c.error_message}</p>
            ) : (
              c.status !== "ready" && (
                <p className="mt-1 text-xs opacity-50">
                  완성되면 저절로 오늘의 학습에 들어가요
                </p>
              )
            )}
          </Link>
        ))}
        {contents.length === 0 && (
          <p className="text-sm opacity-50">
            아직 담은 콘텐츠가 없어요. 라이브러리에서 마음에 드는 영상을 담으면
            오늘의 학습에 들어와요.
          </p>
        )}
      </div>
    </main>
  );
}
