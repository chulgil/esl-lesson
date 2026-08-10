"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
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

type Level = keyof typeof DIFFICULTY_LABELS;
const LEVELS = Object.keys(DIFFICULTY_LABELS) as Level[];
const LEVEL_ORDER: Record<Level, number> = {
  beginner: 0,
  intermediate: 1,
  advanced: 2,
};

/** 학습 난이도(study_level 1-4) -> 콘텐츠 레벨 — 신규 기본(2)이 초급 (level-fit-library) */
function levelOfStudyLevel(studyLevel: number): Level {
  if (studyLevel <= 2) return "beginner";
  return studyLevel === 3 ? "intermediate" : "advanced";
}

/** 맞음 점수 — 이해 가능 입력(i+1): 내 레벨 ±1단 + 아는 표현 60~85% 가 최적 */
function fitScore(c: LibraryContent, myLevel: Level | null): number {
  if (!myLevel) return 0;
  let score = 0;
  if (c.difficulty) {
    const dist = Math.abs(LEVEL_ORDER[c.difficulty] - LEVEL_ORDER[myLevel]);
    score += dist === 0 ? 2 : dist === 1 ? 1 : 0;
  }
  if (c.known_ratio !== null) {
    score +=
      c.known_ratio >= 60 && c.known_ratio <= 85
        ? 2
        : c.known_ratio >= 40
          ? 1
          : 0;
  }
  return score;
}

export default function LibraryPage() {
  return (
    <Suspense>
      <LibraryInner />
    </Suspense>
  );
}

function LibraryInner() {
  // 딥링크 ?level= (온보딩·추천에서 재사용 — level-fit-library-2026-08.md)
  const urlLevel = useSearchParams().get("level");
  const [contents, setContents] = useState<LibraryContent[]>([]);
  // 콘텐츠별 열린 시험 — 카드에 시험 칩(1위·내 최고점) 노출 (2026-07-31 goal)
  const [examByContent, setExamByContent] = useState<Map<number, OpenExam>>(
    new Map(),
  );
  const [error, setError] = useState<string | null>(null);
  const [myLevel, setMyLevel] = useState<Level | null>(null);
  // "all" = 전체 — 기본은 내 레벨 (URL 파라미터가 있으면 그것부터)
  const [filter, setFilter] = useState<Level | "all">(
    LEVELS.includes(urlLevel as Level) ? (urlLevel as Level) : "all",
  );
  const [touched, setTouched] = useState(Boolean(urlLevel));

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
    studyApi
      .getSettings()
      .then((s) => setMyLevel(levelOfStudyLevel(s.study_level)))
      .catch(() => undefined);
  }, []);

  // 내 레벨이 도착하면 기본 필터로 — 사용자가 이미 골랐으면 존중
  useEffect(() => {
    if (myLevel && !touched) setFilter(myLevel);
  }, [myLevel, touched]);

  // 내게 맞는 순 정렬 (fit 내림차순, 동점은 API 순서 유지) + 필터
  const visible = contents
    .filter((c) => filter === "all" || c.difficulty === filter)
    .map((c, i) => ({ c, i, fit: fitScore(c, myLevel) }))
    .sort((a, b) => b.fit - a.fit || a.i - b.i);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-12 sm:px-16">
      <header className="mb-8 flex items-center gap-4">
        <h1 className="font-hand text-4xl font-bold">
          <span className="hl">콘텐츠 라이브러리</span>
        </h1>
      </header>

      {error && <p className="text-sm text-brick-red">{error}</p>}

      {/* 난이도 필터 — 기본 = 내 레벨 (level-fit-library-2026-08.md MVP) */}
      <div className="mb-5 flex flex-wrap items-center gap-2">
        {(["all", ...LEVELS] as const).map((level) => (
          <button
            key={level}
            type="button"
            onClick={() => {
              setTouched(true);
              setFilter(level as Level | "all");
            }}
            className={`min-h-10 rounded-full border-2 px-4 py-1.5 text-sm font-bold transition ${
              filter === level
                ? "border-brick-blue bg-brick-blue/10 text-brick-blue"
                : "border-ink/15 bg-white hover:border-brick-blue/50"
            }`}
          >
            {level === "all" ? "전체" : DIFFICULTY_LABELS[level as Level]}
            {level !== "all" && level === myLevel && (
              <span className="ml-1 text-xs font-normal opacity-60">
                내 레벨
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map(({ c, fit }, i) => (
          <div
            key={c.id}
            className={`flex flex-col rounded-lg border-2 bg-white p-4 shadow-sm transition hover:shadow-md ${
              fit >= 4 ? "border-brick-yellow" : "border-ink/10"
            } ${i % 2 ? "rotate-[0.4deg]" : "-rotate-[0.4deg]"}`}
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
                {/* 이해 가능 입력(i+1) 적합 — 내 레벨 ±1 + 아는 표현 60~85% */}
                {fit >= 4 && (
                  <span className="rounded bg-brick-yellow/40 px-1.5 py-0.5 font-bold">
                    지금 내 수준
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
          <div className="flex flex-col gap-2">
            <p className="text-sm opacity-50">아직 준비된 콘텐츠가 없어요.</p>
            {/* 빈 화면에서 방법을 만나게 — 담을 게 없는 순간이 "왜 이 앱인가"를
                읽어볼 유일한 여유 시간이다 (effectiveness-audit 3차 구멍 4) */}
            <Link
              href="/method"
              className="text-sm font-bold text-brick-blue underline-offset-2 hover:underline"
            >
              이 앱이 영어를 늘리는 방법 보기 →
            </Link>
          </div>
        )}
        {/* 레벨 빈 상태 = 공급 신호 — 숨기지 않고 요청 폼(하단)으로 되돌린다 */}
        {contents.length > 0 && visible.length === 0 && filter !== "all" && (
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm opacity-60">
              {DIFFICULTY_LABELS[filter]} 영상이 아직 없어요 — 아래 요청 폼으로
              보고 싶은 영상을 알려주세요.
            </p>
            <button
              type="button"
              onClick={() => {
                setTouched(true);
                setFilter("all");
              }}
              className="text-sm font-bold text-brick-blue underline-offset-2 hover:underline"
            >
              전체 보기 →
            </button>
          </div>
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
