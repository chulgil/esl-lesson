"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { CrownIcon } from "@/components/exam/ExamEntryCard";
import { ExamRankings } from "@/components/exam/ExamRankings";
import { ExamResult } from "@/components/exam/ExamResult";
import { ExamTimer } from "@/components/exam/ExamTimer";
import { OmrGrid } from "@/components/exam/OmrGrid";
import { BackLink } from "@/components/nav/BackLink";
import {
  examApi,
  type ExamGraded,
  type ExamQuestion,
  type ExamSummary,
} from "@/lib/exam-api";
import { type AppTheme, useAppTheme } from "@/lib/theme";

/** 시험지 화면 — OMR 답안지 컨셉 (docs/specs/library-exam.md).
 *  intro(요약) -> taking(문항+마킹 그리드) -> result(도장·복기) -> rankings.
 *  채점은 전부 서버 — 이 화면은 마킹만 수집해 answers 배열로 제출한다. */

type Phase = "intro" | "taking" | "result" | "rankings";

const MODE_LABELS: Record<string, string> = {
  choice_en2ko: "뜻 고르기",
  choice_ko2en: "영어 고르기",
  cloze: "빈칸 채우기",
  pattern: "문장 고르기",
};

const CHOICE_MARKS = ["1", "2", "3", "4"];

/** 테마별 시험지 스킨 — 같은 레이아웃(문항+OMR)에 표면 컨셉만 바꾼다 (2026-07-31 요청).
 *  노트=종이 시험지 / 캔디=화이트보드(마커) / 레고=블록판(스터드) /
 *  헤냥이=칠판(분필) / 오피스=평가서 시트(위장). OMR·채점 로직은 공통. */
const EXAM_SKINS: Record<
  AppTheme,
  {
    section: string;
    band: string;
    bandTitle: string;
    bandMeta: string;
    divider: string;
    number: string;
    prompt: string;
    promptSub: string;
    choice: string;
    choiceSelected: string;
    mark: string;
    markSelected: string;
    studs?: boolean;
    paw?: boolean;
  }
> = {
  note: {
    section: "rounded-lg border-2 border-ink/15 bg-white",
    band: "border-4 border-double border-ink/50 px-3 py-2 text-center",
    bandTitle: "font-hand text-lg leading-tight font-bold",
    bandMeta: "mt-0.5 text-[10px] tracking-widest opacity-60",
    divider: "mb-3 border-b border-dashed border-ink/25",
    number: "text-xs font-bold opacity-60",
    prompt: "text-lg font-medium",
    promptSub: "mt-1 text-sm opacity-60",
    choice: "border-ink/20 bg-white hover:border-brick-blue/60",
    choiceSelected: "border-brick-blue bg-brick-blue/10 font-bold",
    mark: "border-ink/30",
    markSelected: "border-brick-blue bg-brick-blue text-white",
  },
  candy: {
    section: "rounded-3xl border-4 border-brick-blue/25 bg-white shadow-inner",
    band: "rounded-full bg-highlight/70 px-4 py-2 text-center",
    bandTitle:
      "font-hand text-lg leading-tight font-bold underline decoration-brick-red/50 decoration-wavy underline-offset-4",
    bandMeta: "mt-0.5 text-[10px] tracking-widest opacity-60",
    divider: "mb-3 border-b-2 border-dotted border-brick-blue/25",
    number: "text-xs font-bold text-brick-red/70",
    prompt: "text-lg font-medium",
    promptSub: "mt-1 text-sm opacity-60",
    choice:
      "rounded-full border-brick-blue/25 bg-white hover:border-brick-red/50",
    choiceSelected: "rounded-full border-brick-red bg-brick-red/10 font-bold",
    mark: "border-brick-blue/40",
    markSelected: "border-brick-red bg-brick-red text-white",
  },
  lego: {
    section: "rounded-md border-4 border-ink bg-white",
    band: "relative rounded-sm border-2 border-ink bg-brick-yellow/60 px-3 pt-3 pb-2 text-center",
    bandTitle: "font-hand text-lg leading-tight font-bold",
    bandMeta: "mt-0.5 text-[10px] tracking-widest opacity-70",
    divider: "mb-3 border-b-2 border-ink/20",
    number: "text-xs font-bold opacity-60",
    prompt: "text-lg font-bold",
    promptSub: "mt-1 text-sm opacity-60",
    choice: "rounded-sm border-ink/40 bg-white hover:border-ink",
    choiceSelected: "rounded-sm border-ink bg-brick-blue/15 font-bold",
    mark: "rounded-sm border-ink/50",
    markSelected: "rounded-sm border-ink bg-brick-blue text-white",
    studs: true,
  },
  cat: {
    // 칠판 — 분필 글씨. 어두운 면이라 텍스트·테두리를 밝게 뒤집는다
    section: "rounded-lg border-8 border-[#6b4a2f] bg-[#2f4640] text-[#f4f1e8]",
    band: "relative border-2 border-dashed border-[#f4f1e8]/50 px-3 py-2 text-center",
    bandTitle: "font-hand text-lg leading-tight font-bold",
    bandMeta: "mt-0.5 text-[10px] tracking-widest opacity-70",
    divider: "mb-3 border-b border-dashed border-[#f4f1e8]/30",
    number: "text-xs font-bold opacity-70",
    prompt: "font-hand text-lg font-medium",
    promptSub: "mt-1 text-sm opacity-70",
    choice: "border-[#f4f1e8]/40 bg-white/5 hover:border-brick-yellow/70",
    choiceSelected: "border-brick-yellow bg-white/15 font-bold",
    mark: "border-[#f4f1e8]/50",
    markSelected: "border-brick-yellow bg-brick-yellow text-ink",
    paw: true,
  },
  excel: {
    // 평가서 시트 위장 — 셀 헤더 스트립 + 격자 느낌
    section: "rounded-sm border border-[#c9cfd6] bg-white font-sans",
    band: "border border-[#c9cfd6] bg-[#e2efda] px-3 py-1.5 text-left",
    bandTitle: "text-sm font-bold text-[#217346]",
    bandMeta: "mt-0 text-[10px] text-[#666]",
    divider: "mb-3 border-b border-[#e3e7eb]",
    number: "text-xs font-bold text-[#666]",
    prompt: "text-base font-medium text-[#24292f]",
    promptSub: "mt-1 text-sm text-[#666]",
    choice: "rounded-sm border-[#c9cfd6] bg-white hover:bg-[#f6f8f9]",
    choiceSelected: "rounded-sm border-[#217346] bg-[#e2efda] font-bold",
    mark: "rounded-sm border-[#c9cfd6]",
    markSelected: "rounded-sm border-[#217346] bg-[#217346] text-white",
  },
};

export default function ExamPage() {
  const { contentId } = useParams<{ contentId: string }>();
  const [phase, setPhase] = useState<Phase>("intro");
  const [summary, setSummary] = useState<ExamSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [attemptId, setAttemptId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<ExamQuestion[]>([]);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [current, setCurrent] = useState(0);
  const [graded, setGraded] = useState<ExamGraded | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // 응시 시작 시각(클라 표시용) — 판정 시간은 서버 started_at 이 정본
  const [startedAt, setStartedAt] = useState<number | null>(null);

  const loadSummary = useCallback(() => {
    examApi
      .summary(Number(contentId))
      .then(setSummary)
      .catch((e) => setError(e.message));
  }, [contentId]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  async function start() {
    if (summary?.exam_id == null) return;
    setError(null);
    try {
      const started = await examApi.start(summary.exam_id);
      setAttemptId(started.attempt_id);
      setQuestions(started.questions);
      setAnswers(Array(started.questions.length).fill(null));
      setCurrent(0);
      setGraded(null);
      setStartedAt(Date.now());
      setPhase("taking");
    } catch (e) {
      // 회차 전환 경합 — archived 시험은 새 응시 불가, 요약을 새로 받는다
      if (e instanceof Error && e.message === "exam_archived") {
        setError(
          "시험지가 새 회차로 바뀌었어요. 새 시험지로 다시 도전해 주세요.",
        );
        loadSummary();
      } else {
        setError(e instanceof Error ? e.message : "응시를 시작하지 못했어요");
      }
    }
  }

  function mark(choice: number) {
    const next = answers.map((a, idx) => (idx === current ? choice : a));
    setAnswers(next);
    // 다음 미마킹 문항으로 자동 이동 — OMR 답안지 흐름
    const following = [...next.keys()].find(
      (idx) => idx > current && next[idx] == null,
    );
    const anyBlank = [...next.keys()].find((idx) => next[idx] == null);
    setCurrent(following ?? anyBlank ?? current);
  }

  async function submit() {
    if (summary?.exam_id == null || attemptId == null || submitting) return;
    if (answers.some((a) => a == null)) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await examApi.submit(
        summary.exam_id,
        attemptId,
        answers as number[],
      );
      setGraded(result);
      setPhase("result");
      loadSummary();
    } catch (e) {
      setError(e instanceof Error ? e.message : "제출하지 못했어요");
    } finally {
      setSubmitting(false);
    }
  }

  const question = questions[current];
  const allMarked = answers.length > 0 && answers.every((a) => a != null);
  const theme = useAppTheme();
  const skin = EXAM_SKINS[theme] ?? EXAM_SKINS.note;

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-5 sm:px-16 sm:py-10">
      <header className="mb-4 flex flex-wrap items-center gap-3 sm:mb-6">
        <BackLink href={`/library/${contentId}`} label="콘텐츠" />
        <h1 className="font-hand text-xl font-bold sm:text-2xl">
          <span className="hl">
            {summary?.round != null ? `제${summary.round}회 시험` : "시험"}
          </span>
        </h1>
        {phase === "taking" && (
          <span className="ml-auto flex items-center gap-3">
            {/* 경과 시계 — 테마별 컨셉 (제한시간 아님, 동점 순위 참고용) */}
            {startedAt != null && <ExamTimer startedAt={startedAt} />}
            <span className="text-sm font-bold text-brick-blue">
              {current + 1} / {questions.length}
            </span>
          </span>
        )}
      </header>

      {error && <p className="mb-3 text-sm text-brick-red">{error}</p>}

      <div className="mx-auto max-w-3xl">
        {phase === "intro" && <Intro summary={summary} onStart={start} />}

        {phase === "taking" && question && (
          // pb: 모바일 하단 고정 OMR 패널 실측 ~200px + iOS 홈바 — 마지막 문항
          // 선지가 패널에 가려지지 않게 (2026-07-31 심층 리뷰)
          <div className="flex flex-col gap-4 pb-[calc(15rem+env(safe-area-inset-bottom))] sm:flex-row sm:items-start sm:pb-0">
            {/* 문항 카드 — 테마별 시험지 스킨 (EXAM_SKINS): 종이/화이트보드/블록판/칠판/평가서 */}
            <section className={`flex-1 p-4 sm:p-5 ${skin.section}`}>
              <div className={`mb-3 ${skin.band}`}>
                {skin.studs && (
                  <span className="absolute -top-1.5 left-1/2 flex -translate-x-1/2 gap-2">
                    {[0, 1, 2, 3].map((i) => (
                      <span
                        key={i}
                        className="h-2.5 w-4 rounded-sm border-2 border-ink bg-brick-yellow"
                      />
                    ))}
                  </span>
                )}
                {skin.paw && <PawPrint />}
                <p className={skin.bandTitle}>
                  {theme === "excel"
                    ? `평가서_${summary?.round ?? 1}회.xlsx`
                    : `제${summary?.round ?? 1}회 어학 평가`}
                </p>
                <p className={skin.bandMeta}>
                  {questions.length}문항 · {questions.length * 5}점 만점 ·
                  제한시간 없음
                </p>
              </div>
              <div className={skin.divider} />
              <p className={`mb-2 ${skin.number}`}>
                {current + 1}번 · {MODE_LABELS[question.quiz_mode] ?? "고르기"}
              </p>
              <p className={skin.prompt}>{question.prompt}</p>
              {question.prompt_ko && (
                <p className={skin.promptSub}>{question.prompt_ko}</p>
              )}
              <ol className="mt-4 flex flex-col gap-2">
                {question.choices.map((choice, idx) => {
                  const selected = answers[current] === idx;
                  return (
                    <li key={idx}>
                      <button
                        type="button"
                        onClick={() => mark(idx)}
                        className={`flex min-h-11 w-full items-center gap-3 rounded-md border-2 px-3 py-2 text-left text-sm transition ${
                          selected ? skin.choiceSelected : skin.choice
                        }`}
                      >
                        <span
                          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold ${
                            selected ? skin.markSelected : skin.mark
                          }`}
                        >
                          {CHOICE_MARKS[idx]}
                        </span>
                        {choice}
                      </button>
                    </li>
                  );
                })}
              </ol>
            </section>

            {/* 답안 마킹 그리드 — 모바일은 하단 고정 */}
            <aside className="fixed inset-x-0 bottom-0 z-10 border-t-2 border-ink/15 bg-paper p-3 sm:static sm:w-56 sm:border-0 sm:bg-transparent sm:p-0">
              <OmrGrid
                total={questions.length}
                answers={answers}
                current={current}
                onJump={setCurrent}
              />
              <button
                type="button"
                onClick={submit}
                disabled={!allMarked || submitting}
                className="mt-2 min-h-11 w-full rounded-md bg-brick-red font-bold text-white shadow-sm transition enabled:hover:opacity-90 disabled:opacity-40"
              >
                {submitting
                  ? "채점 중..."
                  : allMarked
                    ? "제출하기"
                    : "전부 마킹하면 제출할 수 있어요"}
              </button>
            </aside>
          </div>
        )}

        {phase === "result" && graded && (
          <ExamResult
            graded={graded}
            questions={questions}
            answers={answers as number[]}
            onRetry={start}
            onShowRankings={() => setPhase("rankings")}
          />
        )}

        {phase === "rankings" && summary?.exam_id != null && (
          <div className="flex flex-col gap-3">
            <button
              type="button"
              onClick={() => setPhase(graded ? "result" : "intro")}
              className="self-start text-sm font-bold text-brick-blue hover:underline"
            >
              &lt; 돌아가기
            </button>
            <ExamRankings examId={summary.exam_id} />
          </div>
        )}
      </div>
    </main>
  );
}

/** 칠판 스킨 장식 — 분필로 그린 고양이 발자국 (헤냥이) */
function PawPrint() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="absolute top-1.5 right-2 h-4 w-4 opacity-50"
      fill="currentColor"
      aria-hidden
    >
      <ellipse cx="12" cy="15" rx="4" ry="3.2" />
      <circle cx="6.5" cy="10" r="1.7" />
      <circle cx="10.2" cy="7.5" r="1.7" />
      <circle cx="13.8" cy="7.5" r="1.7" />
      <circle cx="17.5" cy="10" r="1.7" />
    </svg>
  );
}

function Intro({
  summary,
  onStart,
}: {
  summary: ExamSummary | null;
  onStart: () => void;
}) {
  if (!summary) return <p className="text-sm opacity-60">불러오는 중...</p>;
  if (summary.exam_id == null) {
    return (
      <p className="rounded-lg border-2 border-dashed border-ink/20 bg-white p-8 text-center text-sm opacity-60">
        시험 준비 중이에요 — 시험지가 만들어지면 도전할 수 있어요
      </p>
    );
  }
  return (
    <div className="rounded-lg border-2 border-ink/15 bg-white p-5">
      <p className="font-hand text-lg font-bold">
        {summary.question_count}문항 · 4지선다 OMR
      </p>
      <p className="mt-1 text-sm opacity-70">
        문항당 5점, 총 {(summary.question_count ?? 0) * 5}점. 제한시간은 없지만
        소요시간이 기록돼 동점일 때 순위를 가른다.
      </p>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <li>
          응시자 <b>{summary.attempt_count}명</b>
        </li>
        {summary.my_best && (
          <li>
            내 최고 <b>{summary.my_best.score}점</b> ({summary.my_best.rank}위)
          </li>
        )}
      </ul>
      {(summary.top?.length ?? 0) > 0 && (
        <ol className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-ink/10 pt-2 text-xs">
          {summary.top!.map((entry, idx) => (
            <li
              key={`${entry.nickname}-${idx}`}
              className="flex items-center gap-1"
            >
              <span className="font-bold">{idx + 1}위</span>
              {idx === 0 && <CrownIcon />}
              {entry.nickname}{" "}
              <span className="opacity-60">{entry.score}점</span>
            </li>
          ))}
        </ol>
      )}
      <button
        type="button"
        onClick={onStart}
        className="mt-4 min-h-11 w-full rounded-md bg-brick-blue font-bold text-white shadow-sm transition hover:opacity-90 sm:w-auto sm:px-8"
      >
        응시 시작
      </button>
    </div>
  );
}
