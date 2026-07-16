"use client";

/** 스트릭 캘린더 — 최근 8주 일별 학습량 잔디 (stats.daily 재활용, P1 데일리 루프) */
export function StreakHeatmap({
  daily,
  savedDays = [],
}: {
  daily: Record<string, number>;
  /** 책갈피로 지킨 날 — 학습 0회지만 스트릭이 유지된 날 (retention-plan.md) */
  savedDays?: string[];
}) {
  const WEEKS = 8;
  const saved = new Set(savedDays);
  const today = new Date();
  // 이번 주 일요일 시작 — 열=주, 행=요일 (GitHub 잔디 방향)
  const end = new Date(today);
  end.setDate(end.getDate() + (6 - end.getDay()));
  const cells: { key: string; count: number; future: boolean }[][] = [];
  for (let w = WEEKS - 1; w >= 0; w -= 1) {
    const col: { key: string; count: number; future: boolean }[] = [];
    for (let d = 0; d < 7; d += 1) {
      const date = new Date(end);
      date.setDate(end.getDate() - w * 7 - (6 - d));
      const key = date.toISOString().slice(0, 10);
      col.push({
        key,
        count: daily[key] ?? 0,
        future: date > today,
      });
    }
    cells.push(col);
  }

  function tone(count: number): string {
    if (count === 0) return "bg-ink/8";
    if (count < 5) return "bg-brick-green/30";
    if (count < 15) return "bg-brick-green/60";
    return "bg-brick-green";
  }

  return (
    <div className="flex items-end gap-1" aria-label="최근 8주 학습 기록">
      {cells.map((col, i) => (
        <div key={i} className="flex flex-col gap-1">
          {col.map((cell) => (
            <span
              key={cell.key}
              title={
                saved.has(cell.key)
                  ? `${cell.key} — 책갈피로 지킨 날`
                  : `${cell.key} — ${cell.count}회`
              }
              className={`h-3 w-3 rounded-[3px] ${
                cell.future
                  ? "bg-transparent"
                  : saved.has(cell.key)
                    ? "bg-brick-yellow/70"
                    : tone(cell.count)
              }`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
