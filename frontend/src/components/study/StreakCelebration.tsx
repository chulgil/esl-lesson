"use client";

import { useEffect, useState } from "react";
import { ShareResultButton } from "@/components/game/ShareResultButton";

/** 스트릭 마일스톤 축하 — 7·14·30·50·100·200·365일 도달 첫 진입에 1회 (retention-plan.md).
 *  축하 순간을 만들어 스트릭을 감정 자산으로 — 공유 카드는 게임 결과와 동일 캔버스 재사용. */

const MILESTONES = [7, 14, 30, 50, 100, 200, 365];
const SEEN_KEY = "esl:streak:milestone-seen";

export function StreakCelebration({ streakDays }: { streakDays: number }) {
  const [milestone, setMilestone] = useState<number | null>(null);

  useEffect(() => {
    if (!streakDays) return;
    const hit = MILESTONES.filter((m) => m <= streakDays).pop();
    if (!hit) return;
    const seen = Number(localStorage.getItem(SEEN_KEY) ?? 0);
    if (hit > seen) {
      localStorage.setItem(SEEN_KEY, String(hit)); // 표시 즉시 기록 — 두 번 조르지 않기
      setMilestone(hit);
    }
  }, [streakDays]);

  useEffect(() => {
    if (milestone == null) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMilestone(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [milestone]);

  if (milestone == null) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-6"
      onClick={() => setMilestone(null)}
      role="dialog"
      aria-modal="true"
      aria-label={`${milestone}일 연속 학습 달성`}
    >
      <div
        className="relative w-full max-w-sm rounded-xl border-2 border-ink/15 bg-paper p-6 text-center shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          aria-label="닫기"
          onClick={() => setMilestone(null)}
          className="absolute top-2 right-2 flex h-11 w-11 items-center justify-center rounded-md text-ink/50 hover:text-ink"
        >
          <svg
            width="20"
            height="20"
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

        <p className="text-sm font-bold opacity-70">연속 학습</p>
        <p className="mt-2 font-hand text-5xl font-bold">
          <span className="hl">{milestone}일</span>
        </p>
        <p className="mt-3 text-sm opacity-80">
          {milestone >= 30
            ? "습관이 실력이 되는 구간이에요 — 정말 대단해요!"
            : "꾸준함이 쌓이고 있어요 — 이 흐름 그대로!"}
        </p>

        <div className="mt-5 flex flex-col items-center gap-2">
          <ShareResultButton
            data={{
              game: "연속 학습",
              headline: `${milestone}일 달성!`,
              lines: [
                { label: "다음 목표", value: nextMilestoneLabel(milestone) },
              ],
              tone: "win",
            }}
          />
        </div>
      </div>
    </div>
  );
}

function nextMilestoneLabel(current: number): string {
  const next = MILESTONES.find((m) => m > current);
  return next ? `${next}일 연속` : "매일 한 걸음";
}
