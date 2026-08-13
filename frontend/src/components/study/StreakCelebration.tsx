"use client";

import { useEffect, useState } from "react";
import { ShareResultButton } from "@/components/game/ShareResultButton";

/** 스트릭 마일스톤 축하 — 7·14·30·50·100·200·365일 도달 첫 진입에 1회 (retention-plan.md).
 *  축하 순간을 만들어 스트릭을 감정 자산으로 — 공유 카드는 게임 결과와 동일 캔버스 재사용.
 *  모달 → 토스트 (2026-08-10 ux-redesign #8): 홈 진입 흐름을 막지 않고 아래에서 축하한다. */

const TOAST_SECONDS = 10;

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

  // 토스트 자동 소멸 — 축하가 홈 사용을 막지 않는다
  useEffect(() => {
    if (milestone == null) return;
    const timer = setTimeout(() => setMilestone(null), TOAST_SECONDS * 1000);
    return () => clearTimeout(timer);
  }, [milestone]);

  if (milestone == null) return null;

  return (
    <div
      className="fixed inset-x-0 bottom-20 z-40 flex justify-center px-4"
      role="status"
      aria-label={`${milestone}일 연속 학습 달성`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl border-2 border-brick-yellow bg-paper px-4 py-3 shadow-lg">
        <p className="font-hand text-2xl font-bold">
          <span className="hl">{milestone}일</span> 연속 학습!
        </p>
        <p className="text-xs opacity-70">
          {milestone >= 30
            ? "습관이 실력이 되는 구간이에요"
            : "꾸준함이 쌓이고 있어요"}
        </p>
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
        <button
          type="button"
          aria-label="닫기"
          onClick={() => setMilestone(null)}
          className="flex min-h-11 min-w-11 items-center justify-center rounded-md text-ink/50 hover:text-ink"
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
    </div>
  );
}

function nextMilestoneLabel(current: number): string {
  const next = MILESTONES.find((m) => m > current);
  return next ? `${next}일 연속` : "매일 한 걸음";
}
