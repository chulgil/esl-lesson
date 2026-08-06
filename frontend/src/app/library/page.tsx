"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ContentRequestForm } from "@/components/content/ContentRequestForm";
import { SubscribeButton } from "@/components/content/SubscribeButton";
import { examApi, type OpenExam } from "@/lib/exam-api";
import { studyApi, type LibraryContent } from "@/lib/study-api";

/** 난이도 배지 — 담기 전에 "내 수준의 영상인가"를 보여준다 (content-governance.md) */
const DIFFICULTY_LABELS = {
  beginner: "초급",
  intermediate: "중급",
  advanced: "고급",
} as const;
const DIFFICULTY_STYLES = {
  beginner: "bg-brick-green/15 text-brick-green",
  intermediate: "bg-brick-blue/15 text-brick-blue",
  advanced: "bg-brick-red/15 text-brick-red",
} as const;

export default function LibraryPage() {
  const [contents, setContents] = useState<LibraryContent[]>([]);
  // 콘텐츠별 열린 시험 — 카드에 시험 칩(1위·내 최고점) 노출 (2026-07-31 goal)
  const [examByContent, setExamByContent] = useState<Map<number, OpenExam>>(
    new Map(),
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    studyApi
      .library()
      .then((res) => setContents(res.items))
      .catch((e) => setError(e.message));
    examApi
      .open()
      .then((res) =>
        setExamByContent(new Map(res.items.map((e) => [e.content_id, e]))),
      )
      .catch(() => undefined);
  }, []);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-12 sm:px-16">
      <header className="mb-8 flex items-center gap-4">
        <h1 className="font-hand text-4xl font-bold">
          <span className="hl">콘텐츠 라이브러리</span>
        </h1>
      </header>

      {error && <p className="text-sm text-brick-red">{error}</p>}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {contents.map((c, i) => (
          <div
            key={c.id}
            className={`flex flex-col rounded-lg border-2 border-ink/10 bg-white p-4 shadow-sm transition hover:shadow-md ${
              i % 2 ? "rotate-[0.4deg]" : "-rotate-[0.4deg]"
            }`}
          >
            <Link href={`/library/${c.id}`} className="block">
              <p className="flex items-center gap-2 text-xs">
                <span className="opacity-50">
                  {c.source === "youtube" ? "유튜브" : "수기"}
                </span>
                {c.mine && (
                  <span className="rounded bg-brick-yellow/40 px-1.5 py-0.5 font-bold">
                    내 것
                  </span>
                )}
                {/* CC 배지 — 재사용 허용 영상 표시 (consult-brief §5 저작자표시 보강) */}
                {c.youtube_license === "creativeCommon" && (
                  <span className="rounded bg-brick-green/15 px-1.5 py-0.5 font-bold text-brick-green">
                    CC BY
                  </span>
                )}
                {c.difficulty && (
                  <span
                    className={`rounded px-1.5 py-0.5 font-bold ${DIFFICULTY_STYLES[c.difficulty]}`}
                  >
                    {DIFFICULTY_LABELS[c.difficulty]}
                  </span>
                )}
              </p>
              <p className="mt-1 font-bold">{c.title}</p>
              <p className="mt-2 flex items-center gap-2 text-xs opacity-60">
                <span>학습 항목 {c.item_count}개</span>
                {c.known_ratio !== null && (
                  <span className="rounded-full bg-ink/10 px-2 py-0.5">
                    아는 표현 {c.known_ratio}%
                  </span>
                )}
              </p>
            </Link>
            {/* 시험 칩 — 도전 상태(내 최고점·1위)를 카드에서 바로 보여준다 */}
            {examByContent.has(c.id) && (
              <Link
                href={`/exam/${c.id}`}
                className="mt-2 inline-flex w-fit items-center gap-1.5 rounded-full border-2 border-brick-red/40 bg-brick-red/5 px-2.5 py-1 text-xs font-bold text-brick-red transition hover:border-brick-red"
              >
                시험 도전
                {(() => {
                  const exam = examByContent.get(c.id)!;
                  if (exam.my_best) return ` · 내 최고 ${exam.my_best.score}점`;
                  if (exam.top_name) return ` · 1위 ${exam.top_name}`;
                  return " · 첫 도전자가 돼보세요";
                })()}
              </Link>
            )}
            {/* 개인 콘텐츠는 이미 내 것이라 담기 대상이 아니다 */}
            {!c.mine && (
              <div className="mt-3">
                <SubscribeButton
                  contentId={c.id}
                  subscribed={c.subscribed}
                  onChange={(on) =>
                    setContents((prev) =>
                      prev.map((x) =>
                        x.id === c.id ? { ...x, subscribed: on } : x,
                      ),
                    )
                  }
                />
              </div>
            )}
          </div>
        ))}
        {contents.length === 0 && !error && (
          <p className="text-sm opacity-50">아직 준비된 콘텐츠가 없어요.</p>
        )}
      </div>

      <p className="mt-10 text-xs opacity-50">
        모든 영상은 유튜브 공식 플레이어로 재생되며 수익은 원저작자에게 귀속돼요
        ·{" "}
        <Link href="/copyright" className="underline underline-offset-2">
          저작권 안내
        </Link>
      </p>
      <ContentRequestForm />
    </main>
  );
}
