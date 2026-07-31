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
import { SURFACE_SKINS, useSurfaceSkin } from "@/lib/theme-surfaces";

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
  // 포기 2단계 확인 — window.confirm 은 브라우저가 대화상자를 차단하면
  // 조용히 false 라 "버튼이 안 먹는" 것처럼 보인다 (2026-07-31 보고)
  const [abandonAsk, setAbandonAsk] = useState(false);

  const loadSummary = useCallback(() => {
    examApi
      .summary(Number(contentId))
      .then(setSummary)
      .catch((e) => setError(e.message));
  }, [contentId]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  // 새로고침·재진입 대비 마킹 임시 저장 (attempt 단위) — 제출·포기 시 제거
  const marksKey = (id: number) => `exam-marks-${id}`;

  function enterTaking(
    started: { attempt_id: number; started_at: string; questions: typeof questions },
    restoreMarks: boolean,
  ) {
    setAttemptId(started.attempt_id);
    setQuestions(started.questions);
    let restored: (number | null)[] | null = null;
    if (restoreMarks) {
      try {
        const raw = localStorage.getItem(marksKey(started.attempt_id));
        const parsed = raw ? (JSON.parse(raw) as (number | null)[]) : null;
        if (parsed && parsed.length === started.questions.length) restored = parsed;
      } catch {
        // 복원 실패는 빈 답안으로 진행
      }
    }
    const marks = restored ?? Array(started.questions.length).fill(null);
    setAnswers(marks);
    const firstBlank = marks.findIndex((a) => a == null);
    setCurrent(firstBlank >= 0 ? firstBlank : 0);
    setGraded(null);
    // 경과 기준 = 서버 저장 시작 시각 — 화면을 떠났다 와도 이어진다 (2026-07-31)
    setStartedAt(Date.parse(started.started_at));
    setAbandonAsk(false);
    setPhase("taking");
  }

  async function start() {
    if (summary?.exam_id == null) return;
    setError(null);
    try {
      // 새로 시작 = 서버가 옛 미제출 attempt 를 삭제 — 그 마킹 키도 정리 (고아 방지)
      const stale = summary.my_open_attempt?.attempt_id;
      const started = await examApi.start(summary.exam_id);
      if (stale != null && stale !== started.attempt_id) {
        localStorage.removeItem(marksKey(stale));
      }
      enterTaking(started, false);
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
    if (attemptId != null) {
      try {
        localStorage.setItem(marksKey(attemptId), JSON.stringify(next));
      } catch {
        // 저장 실패해도 응시는 계속
      }
    }
    // 다음 미마킹 문항으로 자동 이동 — OMR 답안지 흐름
    const following = [...next.keys()].find(
      (idx) => idx > current && next[idx] == null,
    );
    const anyBlank = [...next.keys()].find((idx) => next[idx] == null);
    setCurrent(following ?? anyBlank ?? current);
  }

  async function resume() {
    const open = summary?.my_open_attempt;
    if (summary?.exam_id == null || !open) return;
    setError(null);
    try {
      const started = await examApi.resume(summary.exam_id, open.attempt_id);
      enterTaking(started, true);
    } catch {
      // 이미 제출/삭제된 attempt — 요약 새로고침 후 새 응시 유도
      loadSummary();
      setError("이어할 응시가 없어요 — 새로 시작해 주세요.");
    }
  }

  async function abandon() {
    if (summary?.exam_id == null || attemptId == null) return;
    setAbandonAsk(false);
    try {
      await examApi.abandon(summary.exam_id, attemptId);
    } catch {
      // 이미 정리된 attempt — 무시하고 처음 화면으로
    }
    localStorage.removeItem(marksKey(attemptId));
    setAttemptId(null);
    setStartedAt(null);
    setPhase("intro");
    loadSummary();
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
      if (attemptId != null) localStorage.removeItem(marksKey(attemptId));
      loadSummary();
    } catch (e) {
      setError(e instanceof Error ? e.message : "제출하지 못했어요");
    } finally {
      setSubmitting(false);
    }
  }

  const question = questions[current];
  const allMarked = answers.length > 0 && answers.every((a) => a != null);
  const skin = useSurfaceSkin();
  const excelDisguise = skin === SURFACE_SKINS.excel;

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
        {phase === "intro" && (
          <Intro summary={summary} onStart={start} onResume={resume} />
        )}

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
                  {excelDisguise
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
                        className={`flex min-h-11 w-full items-center gap-3 border-2 px-3 py-2 text-left text-sm transition ${skin.radius} ${
                          selected ? skin.choiceSelected : skin.choice
                        }`}
                      >
                        <span
                          className={`flex h-6 w-6 shrink-0 items-center justify-center border-2 text-xs font-bold ${skin.radius} ${
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
                className="mt-2 min-h-11 w-full rounded-md bg-brick-red font-bold text-brick-label shadow-sm transition enabled:hover:opacity-90 disabled:opacity-40"
              >
                {submitting
                  ? "채점 중..."
                  : allMarked
                    ? "제출하기"
                    : "전부 마킹하면 제출할 수 있어요"}
              </button>
              {abandonAsk ? (
                <div className="mt-1.5 flex gap-1.5">
                  <button
                    type="button"
                    onClick={abandon}
                    className="min-h-9 flex-1 rounded-md border-2 border-brick-red bg-white text-xs font-bold text-brick-red transition hover:bg-brick-red hover:text-brick-label"
                  >
                    정말 포기 (경과 초기화)
                  </button>
                  <button
                    type="button"
                    onClick={() => setAbandonAsk(false)}
                    className="min-h-9 flex-1 rounded-md border-2 border-ink/20 bg-white text-xs font-bold"
                  >
                    계속 풀기
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setAbandonAsk(true)}
                  className="mt-1.5 min-h-9 w-full text-xs opacity-50 hover:underline hover:opacity-80"
                >
                  포기하기 (경과 초기화)
                </button>
              )}
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
  onResume,
}: {
  summary: ExamSummary | null;
  onStart: () => void;
  onResume: () => void;
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
      <div className="mt-4 flex flex-wrap gap-2">
        {summary.my_open_attempt ? (
          <>
            {/* 진행 중 응시 — 경과는 서버 시작 시각부터 이어진다 (포기해야 초기화) */}
            <button
              type="button"
              onClick={onResume}
              className="min-h-11 rounded-md bg-brick-blue px-6 font-bold text-brick-label shadow-sm transition hover:opacity-90"
            >
              이어서 응시 (경과 계속)
            </button>
            <button
              type="button"
              onClick={onStart}
              className="min-h-11 rounded-md border-2 border-ink/25 bg-white px-4 font-bold transition hover:border-brick-red hover:text-brick-red"
            >
              새로 시작
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={onStart}
            className="min-h-11 w-full rounded-md bg-brick-blue font-bold text-brick-label shadow-sm transition hover:opacity-90 sm:w-auto sm:px-8"
          >
            응시 시작
          </button>
        )}
      </div>
    </div>
  );
}
