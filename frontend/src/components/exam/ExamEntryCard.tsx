"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { examApi, type ExamSummary } from "@/lib/exam-api";

/** 라이브러리 상세 진입점 — 활성 시험 요약(응시자·내 최고점·TOP3) + [시험 보기].
 *  시험이 없으면 "시험 준비 중" (오류 아님, 시나리오 4). */
export function ExamEntryCard({ contentId }: { contentId: number }) {
  const [summary, setSummary] = useState<ExamSummary | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    examApi
      .summary(contentId)
      .then(setSummary)
      .catch(() => setFailed(true));
  }, [contentId]);

  // 요약 로드 실패는 학습 화면을 막지 않는다 — 카드만 숨김
  if (failed || !summary) return null;

  if (summary.exam_id == null) {
    return (
      <div className="rounded-lg border-2 border-dashed border-ink/20 bg-white p-4 text-center text-sm opacity-60">
        시험 준비 중 — 시험지가 만들어지면 여기서 도전할 수 있어요
      </div>
    );
  }

  return (
    <div className="rounded-lg border-2 border-ink/15 bg-white p-4">
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <p className="font-hand text-lg font-bold">
            제{summary.round}회 시험
          </p>
          <p className="text-xs opacity-60">
            {summary.question_count}문항 · 응시자 {summary.attempt_count}명
            {summary.my_best
              ? ` · 내 최고 ${summary.my_best.score}점 (${summary.my_best.rank}위)`
              : ""}
          </p>
        </div>
        <Link
          href={`/exam/${contentId}`}
          className="ml-auto flex min-h-11 items-center rounded-md bg-brick-blue px-5 font-bold text-brick-label shadow-sm transition hover:opacity-90"
        >
          시험 보기
        </Link>
      </div>
      {(summary.top?.length ?? 0) > 0 && (
        <ol className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-ink/10 pt-2 text-xs">
          {summary.top!.map((entry, idx) => (
            <li
              key={`${entry.nickname}-${idx}`}
              className="flex items-center gap-1"
            >
              <span className="font-bold">
                {idx === 0 ? "1위" : `${idx + 1}위`}
              </span>
              {idx === 0 && <CrownIcon />}
              <span>{entry.nickname}</span>
              <span className="opacity-60">{entry.score}점</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export function CrownIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-3.5 w-3.5 text-brick-yellow"
      fill="currentColor"
      stroke="currentColor"
      strokeWidth="1"
      aria-hidden
    >
      <path d="M3 8l4 4 5-6 5 6 4-4-1.5 10h-15L3 8z" />
    </svg>
  );
}
