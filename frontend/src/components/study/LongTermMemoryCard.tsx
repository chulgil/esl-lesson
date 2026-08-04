import type { LongTermMemory } from "@/lib/study-api";

/** 장기 기억 — stability 7일+ 카드 수 + 8주 도달 누적 브릭 바
 * (docs/specs/learning.md 장기 기억 지표, 기획: duolingo-benchmark-2026-08.md) */
export function LongTermMemoryCard({ data }: { data: LongTermMemory }) {
  const weekly = data.weekly;
  const max = Math.max(1, ...weekly.map((w) => w.count));
  const thisWeekGain =
    weekly.length >= 2
      ? weekly[weekly.length - 1].count - weekly[weekly.length - 2].count
      : 0;

  return (
    <div className="mt-4 rounded-md border-2 border-brick-green/40 bg-brick-green/5 px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-sm font-bold">장기 기억</span>
        <span className="font-hand text-2xl font-bold text-brick-green">
          {data.count}개
        </span>
        {thisWeekGain > 0 && (
          <span className="rounded bg-brick-green/15 px-1.5 py-0.5 text-xs font-bold text-brick-green">
            이번 주 +{thisWeekGain}
          </span>
        )}
      </div>
      <p className="mt-0.5 text-xs opacity-60">
        일주일 넘게 안 봐도 기억하는 카드 — 복습이 쌓아 올린 진짜 실력이에요
      </p>
      {weekly.some((w) => w.count > 0) && (
        <div
          className="mt-2 flex h-10 items-end gap-1"
          aria-label="최근 8주 장기 기억 도달 누적"
        >
          {weekly.map((w) => (
            <div
              key={w.week_start}
              title={`${w.week_start} 주까지 ${w.count}개`}
              className="flex-1 rounded-sm bg-brick-green/70"
              style={{ height: `${Math.max(10, (w.count / max) * 100)}%` }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
