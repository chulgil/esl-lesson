"use client";

/** 스트릭 캘린더 — 이번 달 잔디 (요일 정렬 달력, stats.daily 재활용).
 *
 *  날짜 기준은 **KST 고정**: 백엔드 stats.daily 키가 KST 날짜라, 브라우저 로컬
 *  시각이나 UTC 로 키를 만들면 어긋난다 (2026-08-03 수정 — toISOString 을 쓰던
 *  구현은 KST 00~09시 사이 잔디 전체가 하루씩 밀렸다). */

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/** KST 기준 오늘 (YYYY-MM-DD) — 서버의 하루 경계와 같은 정의 */
function kstToday(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

const pad = (n: number) => String(n).padStart(2, "0");

export function StreakHeatmap({
  daily,
  savedDays = [],
}: {
  daily: Record<string, number>;
  /** 책갈피로 지킨 날 — 학습 0회지만 스트릭이 유지된 날 (retention-plan.md) */
  savedDays?: string[];
}) {
  const saved = new Set(savedDays);
  const [year, month, today] = kstToday().split("-").map(Number);
  // 요일·말일 계산은 UTC 로 — 로컬 시간대가 끼어들 여지를 없앤다
  const firstWeekday = new Date(Date.UTC(year, month - 1, 1)).getUTCDay();
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();

  function tone(count: number): string {
    if (count === 0) return "bg-ink/8";
    if (count < 5) return "bg-brick-green/30";
    if (count < 15) return "bg-brick-green/60";
    return "bg-brick-green";
  }

  const cellOf = (y: number, m: number, day: number, prevMonth = false) => {
    const key = `${y}-${pad(m)}-${pad(day)}`;
    return {
      key,
      count: daily[key] ?? 0,
      saved: saved.has(key),
      future: !prevMonth && day > today,
      isToday: !prevMonth && day === today,
      prevMonth,
    };
  };

  // 1일 앞 칸은 지난달 말일들로 채운다 — 달력 첫 줄이 비어 보이지 않게 (흐리게 표시)
  const prevYear = month === 1 ? year - 1 : year;
  const prevMonth = month === 1 ? 12 : month - 1;
  const prevLastDay = new Date(Date.UTC(prevYear, prevMonth, 0)).getUTCDate();
  const leading = Array.from({ length: firstWeekday }, (_, i) =>
    cellOf(prevYear, prevMonth, prevLastDay - firstWeekday + 1 + i, true),
  );
  const days = Array.from({ length: lastDay }, (_, i) =>
    cellOf(year, month, i + 1),
  );

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <p className="text-xs font-bold opacity-70">
          {year}년 {month}월
        </p>
        <p className="flex items-center gap-1 text-[10px] opacity-50">
          적음
          <span className="h-2 w-2 rounded-[2px] bg-ink/8" />
          <span className="h-2 w-2 rounded-[2px] bg-brick-green/30" />
          <span className="h-2 w-2 rounded-[2px] bg-brick-green/60" />
          <span className="h-2 w-2 rounded-[2px] bg-brick-green" />
          많음
        </p>
      </div>
      <div
        className="grid w-fit grid-cols-7 gap-1"
        role="group"
        aria-label={`${year}년 ${month}월 학습 기록`}
      >
        {WEEKDAYS.map((w, i) => (
          <span
            key={w}
            className={`w-4 text-center text-[10px] ${
              i === 0 || i === 6 ? "opacity-40" : "opacity-60"
            }`}
            aria-hidden
          >
            {w}
          </span>
        ))}
        {[...leading, ...days].map((cell) => (
          <span
            key={cell.key}
            aria-hidden
            title={
              cell.saved
                ? `${cell.key} — 책갈피로 지킨 날`
                : cell.future
                  ? cell.key
                  : `${cell.key} — ${cell.count}회`
            }
            className={`h-4 w-4 rounded-[3px] ${
              cell.isToday ? "ring-2 ring-brick-blue ring-offset-1" : ""
            } ${cell.prevMonth ? "opacity-30" : ""} ${
              cell.future
                ? "border border-dashed border-ink/15"
                : cell.saved
                  ? "bg-brick-yellow/70"
                  : tone(cell.count)
            }`}
          />
        ))}
      </div>
    </div>
  );
}
