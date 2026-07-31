"use client";

import { useEffect, useState } from "react";
import { useAppTheme } from "@/lib/theme";
import { CLOCK_OF } from "@/lib/theme-surfaces";

/** 응시 경과 시계 — 제한시간은 없고 "지금까지 몇 분째" 를 보여준다
 *  (동점 순위는 소요시간이 가르므로 인지 가치가 있음, 2026-07-31 요청).
 *  판정용 시간은 서버(started_at~submit)가 정본 — 이 표시는 안내용.
 *  테마별 시계 컨셉: 노트=벽시계, 캔디=막대사탕, 레고=디지털 브릭,
 *  헤냥이=고양이 시계, 오피스=상태바 셀. */
export function ExamTimer({ startedAt }: { startedAt: number }) {
  const theme = useAppTheme();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const secs = Math.max(0, Math.floor((now - startedAt) / 1000));
  const mm = String(Math.floor(secs / 60)).padStart(2, "0");
  const ss = String(secs % 60).padStart(2, "0");
  const label = `${mm}:${ss}`;

  const clock = CLOCK_OF[theme] ?? "analog";
  if (clock === "cell") {
    // 셀/상태바 위장 — 문서 느낌 유지
    return (
      <span className="inline-flex min-h-8 items-center rounded-sm border border-[#c9cfd6] bg-[#f6f8f9] px-2 font-mono text-xs text-[#217346]">
        경과 {label}
      </span>
    );
  }
  if (clock === "digital") {
    // 디지털 브릭 타이머 — 스터드 2개 + 모노 숫자
    return (
      <span className="relative inline-flex min-h-8 items-center rounded-md border-2 border-ink bg-brick-red px-2.5 pt-1 font-mono text-sm font-bold text-brick-label">
        <span className="absolute -top-1.5 left-2 h-2 w-3 rounded-sm border-2 border-ink bg-brick-red" />
        <span className="absolute -top-1.5 right-2 h-2 w-3 rounded-sm border-2 border-ink bg-brick-red" />
        {label}
      </span>
    );
  }

  // 아날로그 시계 (노트=벽시계 / 캔디=막대사탕 / 헤냥이=고양이 귀)
  const minuteDeg = (secs / 60) * 6; // 60분에 한 바퀴
  const secondDeg = secs * 6;
  return (
    <span className="inline-flex items-center gap-1.5 text-sm font-bold">
      <svg
        viewBox="0 0 24 30"
        className="h-7 w-6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        aria-hidden
      >
        {clock === "analog-cat" && (
          // 고양이 귀
          <>
            <path
              d="M6 9L4 3l6 3"
              fill="currentColor"
              stroke="none"
              opacity="0.85"
            />
            <path
              d="M18 9l2-6-6 3"
              fill="currentColor"
              stroke="none"
              opacity="0.85"
            />
          </>
        )}
        {clock === "analog-candy" && (
          // 막대사탕 손잡이
          <path d="M12 22v7" strokeWidth="2.2" />
        )}
        <circle cx="12" cy="14" r="8.5" fill="var(--color-paper, #fff)" />
        {clock === "analog-candy" && (
          // 사탕 소용돌이
          <path
            d="M12 14a3 3 0 013-3 5 5 0 00-8 4 6.5 6.5 0 0010 4"
            opacity="0.35"
          />
        )}
        {clock === "analog-cat" && (
          // 수염
          <>
            <path
              d="M1.5 13.5h3M1.5 16h3M19.5 13.5h3M19.5 16h3"
              opacity="0.5"
              strokeWidth="1"
            />
          </>
        )}
        {/* 분침·초침 — 실시간 회전 */}
        <line
          x1="12"
          y1="14"
          x2="12"
          y2="9.5"
          transform={`rotate(${minuteDeg} 12 14)`}
        />
        <line
          x1="12"
          y1="14"
          x2="12"
          y2="8"
          transform={`rotate(${secondDeg} 12 14)`}
          strokeWidth="1"
          opacity="0.6"
        />
        <circle cx="12" cy="14" r="0.9" fill="currentColor" stroke="none" />
      </svg>
      {label}
    </span>
  );
}
