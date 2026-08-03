"use client";

import { useEffect, useRef } from "react";

/** 스트릭 잔디 — GitHub 컨트리뷰션 그래프식 1년(53주) 뷰.
 *
 *  열=주, 행=요일(일~토), 상단에 월 라벨. 좁은 화면은 가로 스크롤이며 진입 시
 *  오른쪽 끝(오늘)으로 스크롤한다.
 *
 *  날짜 기준은 **KST 고정**: 백엔드 stats.daily 키가 KST 날짜라, 브라우저 로컬
 *  시각이나 UTC 로 키를 만들면 어긋난다 (2026-08-03 수정 — toISOString 을 쓰던
 *  구현은 KST 00~09시 사이 잔디 전체가 하루씩 밀렸다). 아래 달력 산술은 KST
 *  오늘을 UTC 자정으로 앵커링해 시간대 영향을 완전히 배제한다. */

const WEEKS = 53;
const DAY_MS = 86_400_000;
const MONTHS = [
  "1월",
  "2월",
  "3월",
  "4월",
  "5월",
  "6월",
  "7월",
  "8월",
  "9월",
  "10월",
  "11월",
  "12월",
];
/** 행 라벨은 월·수·금만 — GitHub 과 같은 밀도 (7줄 다 쓰면 글자가 칸보다 크다) */
const ROW_LABELS = ["", "월", "", "수", "", "금", ""];

const pad = (n: number) => String(n).padStart(2, "0");

/** KST 기준 오늘을 UTC 자정 타임스탬프로 — 서버의 하루 경계와 같은 정의 */
function kstTodayAnchor(): number {
  const [y, m, d] = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })
    .format(new Date())
    .split("-")
    .map(Number);
  return Date.UTC(y, m - 1, d);
}

export function StreakHeatmap({
  daily,
  savedDays = [],
}: {
  daily: Record<string, number>;
  /** 책갈피로 지킨 날 — 학습 0회지만 스트릭이 유지된 날 (retention-plan.md) */
  savedDays?: string[];
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const saved = new Set(savedDays);
  const today = kstTodayAnchor();
  // 이번 주 토요일에서 끝나는 53주 — 마지막 열에 오늘이 들어온다
  const end = today + (6 - new Date(today).getUTCDay()) * DAY_MS;
  const start = end - (WEEKS * 7 - 1) * DAY_MS;

  const weeks = Array.from({ length: WEEKS }, (_, w) =>
    Array.from({ length: 7 }, (_, d) => {
      const ts = start + (w * 7 + d) * DAY_MS;
      const date = new Date(ts);
      const key = `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
      return {
        key,
        month: date.getUTCMonth(),
        count: daily[key] ?? 0,
        saved: saved.has(key),
        future: ts > today,
        isToday: ts === today,
      };
    }),
  );

  // 월 라벨 — 그 주의 첫날(일요일) 기준으로 달이 바뀐 열에만 표기
  const monthLabels = weeks.map((week, i) => {
    if (i === 0) return week[0].month;
    return week[0].month !== weeks[i - 1][0].month ? week[0].month : null;
  });

  // 진입 시 오늘(오른쪽 끝)이 보이게 — 좁은 화면 기본 시야가 1년 전이면 무의미.
  // 회전·창 크기 변경에도 다시 맞춘다
  useEffect(() => {
    const toEnd = () => {
      const el = scrollRef.current;
      if (el) el.scrollLeft = el.scrollWidth;
    };
    toEnd();
    window.addEventListener("resize", toEnd);
    return () => window.removeEventListener("resize", toEnd);
  }, []);

  function tone(count: number): string {
    if (count === 0) return "bg-ink/8";
    if (count < 5) return "bg-brick-green/30";
    if (count < 15) return "bg-brick-green/60";
    return "bg-brick-green";
  }

  const total = Object.entries(daily).reduce(
    (sum, [key, n]) => (key >= weeks[0][0].key ? sum + n : sum),
    0,
  );

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <p className="text-xs font-bold opacity-70">
          최근 1년 · {total}회 학습
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

      <div className="flex gap-1">
        {/* 요일 라벨 — 월 라벨 줄(14px)만큼 내려서 행을 맞춘다 */}
        <div className="mt-[14px] flex shrink-0 flex-col gap-[3px]" aria-hidden>
          {ROW_LABELS.map((label, i) => (
            <span
              key={i}
              className="flex h-2.5 items-center text-[9px] leading-none opacity-50"
            >
              {label}
            </span>
          ))}
        </div>

        <div
          ref={scrollRef}
          className="overflow-x-auto"
          role="group"
          aria-label={`최근 1년 학습 기록 — 총 ${total}회`}
        >
          <div className="inline-flex flex-col gap-1">
            <div className="flex gap-[3px]">
              {monthLabels.map((month, i) => (
                <span
                  key={i}
                  className="relative h-[10px] w-2.5 shrink-0"
                  aria-hidden
                >
                  {month !== null && (
                    <span className="absolute left-0 text-[9px] leading-none whitespace-nowrap opacity-50">
                      {MONTHS[month]}
                    </span>
                  )}
                </span>
              ))}
            </div>
            <div className="flex gap-[3px]">
              {weeks.map((week, i) => (
                <div key={i} className="flex shrink-0 flex-col gap-[3px]">
                  {week.map((cell) => (
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
                      className={`h-2.5 w-2.5 rounded-[2px] ${
                        cell.isToday
                          ? "ring-1 ring-brick-blue ring-offset-1"
                          : ""
                      } ${
                        cell.future
                          ? "bg-transparent"
                          : cell.saved
                            ? "bg-brick-yellow/70"
                            : tone(cell.count)
                      }`}
                    />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
