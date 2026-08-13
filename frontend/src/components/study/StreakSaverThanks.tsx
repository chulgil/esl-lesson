"use client";

import { useEffect, useState } from "react";

/** 복귀 감사 배너 — 책갈피가 스트릭을 지켜준 다음 방문에 1회.
 *  "안 끊겼다"는 안도감 + 책갈피의 가치 학습 (user-journey-motivation P1).
 *  모달 금지 — 홈의 오늘 할 일을 가리지 않는 조용한 한 줄. */

const SEEN_KEY = "esl:streak:saver-thanked";
const RECENT_DAYS = 7;

export function StreakSaverThanks({
  savedDays,
  streakDays,
}: {
  savedDays: string[];
  streakDays: number;
}) {
  const [shownDay, setShownDay] = useState<string | null>(null);

  useEffect(() => {
    if (!savedDays.length) return;
    const latest = savedDays[savedDays.length - 1]; // 백엔드가 정렬해 내려줌
    const ageDays =
      (Date.now() - new Date(`${latest}T00:00:00+09:00`).getTime()) /
      86_400_000;
    if (ageDays > RECENT_DAYS) return; // 오래된 보호를 새삼 꺼내지 않는다
    if (localStorage.getItem(SEEN_KEY) === latest) return;
    localStorage.setItem(SEEN_KEY, latest); // 표시 즉시 기록 — 두 번 조르지 않기
    setShownDay(latest);
  }, [savedDays]);

  if (!shownDay) return null;
  const [, month, day] = shownDay.split("-");

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border-2 border-brick-yellow/60 bg-highlight/30 px-4 py-2.5 text-sm">
      <span>
        {Number(month)}월 {Number(day)}일, 책갈피가 하루를 지켜줬어요 —{" "}
        <b>{streakDays}일 연속</b>이 계속되고 있어요
      </span>
      <button
        type="button"
        aria-label="닫기"
        onClick={() => setShownDay(null)}
        className="ml-auto flex min-h-11 min-w-11 items-center justify-center rounded-md text-ink/50 hover:text-ink"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          aria-hidden
        >
          <path d="M18 6 6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
