"use client";

import { useEffect, useState } from "react";
import { CrownIcon } from "@/components/exam/ExamEntryCard";
import { formatDuration } from "@/components/exam/ExamResult";
import { examApi, type ExamRankings as ExamRankingsData } from "@/lib/exam-api";

/** 랭킹 보드 — TOP 50 + 내 순위 고정행, 1위 왕관 (docs/specs/library-exam.md) */
export function ExamRankings({ examId }: { examId: number }) {
  const [data, setData] = useState<ExamRankingsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    examApi
      .rankings(examId)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [examId]);

  if (error) return <p className="text-sm text-brick-red">{error}</p>;
  if (!data) return <p className="text-sm opacity-60">불러오는 중...</p>;
  if (data.items.length === 0) {
    return (
      <p className="rounded-lg border-2 border-dashed border-ink/20 bg-white p-6 text-center text-sm opacity-60">
        아직 제출한 사람이 없어요 — 첫 번째 주인공이 되어 보세요
      </p>
    );
  }

  const meOutsideTop = data.me && !data.items.some((r) => r.is_me);
  return (
    <div className="overflow-hidden rounded-lg border-2 border-ink/15 bg-white">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b-2 border-ink/15 text-left text-xs opacity-70">
            <th className="w-14 p-2">순위</th>
            <th className="p-2">닉네임</th>
            <th className="w-16 p-2 text-right">점수</th>
            <th className="w-24 p-2 text-right">소요</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((row) => (
            <RankRow key={row.rank} row={row} />
          ))}
          {meOutsideTop && data.me && (
            <>
              <tr>
                <td colSpan={4} className="p-1 text-center text-xs opacity-40">
                  ...
                </td>
              </tr>
              <RankRow row={data.me} />
            </>
          )}
        </tbody>
      </table>
    </div>
  );
}

function RankRow({
  row,
}: {
  row: {
    rank: number;
    nickname: string;
    score: number;
    duration_ms: number;
    is_me: boolean;
  };
}) {
  return (
    <tr
      className={`border-b border-ink/10 last:border-b-0 ${
        row.is_me ? "bg-highlight/40 font-bold" : ""
      }`}
    >
      <td className="p-2">
        <span className="flex items-center gap-1">
          {row.rank}위{row.rank === 1 && <CrownIcon />}
        </span>
      </td>
      <td className="p-2">
        {row.nickname}
        {row.is_me && (
          <span className="ml-1 text-xs text-brick-blue">(나)</span>
        )}
      </td>
      <td className="p-2 text-right">{row.score}점</td>
      <td className="p-2 text-right text-xs opacity-70">
        {formatDuration(row.duration_ms)}
      </td>
    </tr>
  );
}
