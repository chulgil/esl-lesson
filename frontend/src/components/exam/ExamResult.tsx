"use client";

import type { ExamGraded, ExamQuestion } from "@/lib/exam-api";

export function formatDuration(ms: number): string {
  const total = Math.round(ms / 1000);
  return `${Math.floor(total / 60)}분 ${total % 60}초`;
}

/** 결과 화면 — 점수 도장 + 정답 복기 + 순위 + [다시 도전]/[랭킹 보기] */
export function ExamResult({
  graded,
  questions,
  answers,
  onRetry,
  onShowRankings,
}: {
  graded: ExamGraded;
  questions: ExamQuestion[];
  answers: number[];
  onRetry: () => void;
  onShowRankings: () => void;
}) {
  const perfect = graded.score === 100;
  return (
    <div className="flex flex-col gap-4">
      {/* 점수 도장 — 시험지에 찍힌 붉은 도장 컨셉 */}
      <div className="flex items-center gap-4 rounded-lg border-2 border-ink/15 bg-white p-4">
        <div
          className={`flex h-24 w-24 shrink-0 -rotate-6 flex-col items-center justify-center rounded-full border-4 ${
            perfect
              ? "border-brick-red text-brick-red"
              : "border-brick-blue text-brick-blue"
          }`}
        >
          <span className="font-hand text-3xl leading-none font-bold">
            {graded.score}
          </span>
          <span className="text-[10px] font-bold">점</span>
        </div>
        <div className="text-sm">
          <p className="font-hand text-xl font-bold">
            {perfect
              ? "만점이에요!"
              : `${graded.correct_count}/${graded.results.length} 문제 정답`}
          </p>
          <p className="mt-1 opacity-70">
            소요 {formatDuration(graded.duration_ms)} · 현재{" "}
            <b className="text-brick-blue">{graded.rank}위</b>
          </p>
          {/* 보상 체감 — 이번 제출로 얻은 XP (제출 20 + 점수 10점당 1) */}
          <p className="mt-1.5">
            <span className="rounded-full bg-brick-green/15 px-2.5 py-1 text-xs font-bold text-brick-green">
              +{graded.xp_gained} XP 획득!
            </span>
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={onRetry}
          className="min-h-11 rounded-md bg-brick-blue px-4 font-bold text-brick-label shadow-sm transition hover:opacity-90"
        >
          다시 도전
        </button>
        <button
          type="button"
          onClick={onShowRankings}
          className="min-h-11 rounded-md border-2 border-ink/25 bg-white px-4 font-bold shadow-sm transition hover:border-brick-blue"
        >
          랭킹 보기
        </button>
      </div>

      {/* 정답 복기 — 문항별 내 마킹 vs 정답 */}
      <ol className="flex flex-col gap-2">
        {questions.map((q, idx) => {
          const result = graded.results[idx];
          const mine = answers[idx];
          return (
            <li
              key={q.seq}
              className={`rounded-lg border-2 bg-white p-3 text-sm ${
                result.correct ? "border-brick-green/40" : "border-brick-red/40"
              }`}
            >
              <p className="flex items-baseline gap-2">
                <span
                  className={`font-bold ${
                    result.correct ? "text-brick-green" : "text-brick-red"
                  }`}
                >
                  {q.seq}. {result.correct ? "정답" : "오답"}
                </span>
                <span className="font-medium">{q.prompt}</span>
              </p>
              {q.prompt_ko && (
                <p className="mt-0.5 text-xs opacity-60">{q.prompt_ko}</p>
              )}
              <p className="mt-1 text-xs">
                {!result.correct && (
                  <>
                    <span className="text-brick-red line-through">
                      내 마킹: {q.choices[mine]}
                    </span>
                    {" -> "}
                  </>
                )}
                <span className="font-bold text-brick-green">
                  정답: {q.choices[result.answer_index]}
                </span>
              </p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
