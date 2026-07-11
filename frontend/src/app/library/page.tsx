"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { studyApi, type LibraryContent } from "@/lib/study-api";

export default function LibraryPage() {
  const [contents, setContents] = useState<LibraryContent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    studyApi
      .library()
      .then((res) => setContents(res.items))
      .catch((e) => setError(e.message));
  }, []);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-12 sm:px-16">
      <header className="mb-8 flex items-center gap-4">
        <Link href="/" className="text-sm opacity-60 hover:underline">
          &lt; 홈
        </Link>
        <h1 className="font-hand text-4xl font-bold">
          <span className="hl">콘텐츠 라이브러리</span>
        </h1>
      </header>

      {error && <p className="text-sm text-brick-red">{error}</p>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {contents.map((c, i) => (
          <Link
            key={c.id}
            href={`/library/${c.id}`}
            className={`rounded-lg border-2 border-ink/10 bg-white p-4 shadow-sm transition hover:-translate-y-1 hover:shadow-md ${
              i % 2 ? "rotate-[0.4deg]" : "-rotate-[0.4deg]"
            }`}
          >
            <p className="text-xs opacity-50">
              {c.source === "youtube" ? "유튜브" : "수기"}
            </p>
            <p className="mt-1 font-bold">{c.title}</p>
            <p className="mt-2 text-xs opacity-60">
              학습 항목 {c.item_count}개
            </p>
          </Link>
        ))}
        {contents.length === 0 && !error && (
          <p className="text-sm opacity-50">아직 준비된 콘텐츠가 없어요.</p>
        )}
      </div>
    </main>
  );
}
