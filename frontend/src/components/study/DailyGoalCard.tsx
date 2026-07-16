"use client";

import Link from "next/link";
import { StreakHeatmap } from "@/components/study/StreakHeatmap";
import type { Stats } from "@/lib/study-api";

/** 오늘의 목표 카드 — 밀린 전체가 아닌 달성 가능한 소량 목표로 유도 (포기 방지 기획).
 *  진행바는 목표 기준 100% 상한: 100개 밀려도 "오늘 20개만"이 목표다. */
function BookmarkIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-brick-yellow-shadow"
      aria-hidden
    >
      <path d="M6 3h12v18l-6-4.5L6 21V3Z" />
    </svg>
  );
}

export function DailyGoalCard({ stats }: { stats: Stats }) {
  const goal = stats.daily_goal || 20;
  const done = stats.reviews_today;
  const met = done >= goal;
  const todayTarget = Math.min(stats.due_count, Math.max(0, goal - done));

  return (
    <div className="max-w-xl rounded-lg border-2 border-ink/10 bg-white p-4">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-bold">
          오늘의 목표
          <span
            className={`ml-2 font-normal ${met ? "font-bold text-brick-green" : "opacity-60"}`}
          >
            {Math.min(done, goal)}/{goal}
            {met && done > goal && ` (+${done - goal})`}
          </span>
        </p>
        <Link
          href="/settings"
          className="text-xs opacity-50 underline-offset-2 hover:underline"
        >
          목표 조정
        </Link>
      </div>
      <div className="mt-2 h-3 overflow-hidden rounded-full bg-ink/10">
        <div
          className="h-full rounded-full bg-brick-green transition-[width]"
          style={{
            width: `${Math.min(100, Math.round((done / goal) * 100))}%`,
          }}
        />
      </div>
      <p className="mt-2 text-xs opacity-70">
        {met
          ? stats.due_count > 0
            ? `오늘 목표 달성! 더 해도 좋아요 — 남은 ${stats.due_count}개는 나눠서 갚으면 돼요`
            : "오늘 목표 달성! 밀린 복습도 없어요"
          : stats.due_count === 0
            ? done > 0
              ? "지금은 밀린 복습이 없어요 — 새 카드로 채워도 좋아요"
              : "지금은 밀린 복습이 없어요"
            : stats.due_count > todayTarget
              ? `오늘은 ${todayTarget}개만 하면 성공 — 밀린 ${stats.due_count}개는 나눠서 갚아요`
              : `오늘은 ${todayTarget}개만 하면 성공`}
      </p>
      <div className="mt-3 border-t border-ink/10 pt-3">
        <StreakHeatmap
          daily={stats.daily}
          savedDays={stats.streak_saved_days}
        />
        {/* 책갈피 — 하루 놓쳐도 자동으로 연속 학습을 지켜주는 보호 장치 */}
        <p
          className="mt-2 flex items-center gap-1 text-xs opacity-70"
          title="하루 놓치면 책갈피가 자동으로 끼워져 연속 학습이 끊기지 않아요. 오늘 목표를 달성하면 매주 1개를 받아요 (최대 2개)."
        >
          <BookmarkIcon />
          책갈피 {stats.streak_savers ?? 0}개
          <span className="opacity-60">
            — 하루 놓쳐도 연속 학습을 지켜줘요 (주 1회 목표 달성 시 지급)
          </span>
        </p>
      </div>
    </div>
  );
}
